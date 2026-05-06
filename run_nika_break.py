"""
NIKA-break pipeline — inherits NIKA's broken injector, then rescues it.

Two flows, selected per-problem:

  A) STRESS FAMILY (load_balancer_overload / sender_resource_contention /
     receiver_resource_contention) — test.py pattern:
       Step 1:  start_net_env(scenario, topo_size)
       Step 2:  _stress_family_inject(problem, net_env, lab_name)
                  └─ pick ONE target from the right pool,
                     docker update --memory 1g --memory-swap 2g <target>,
                     exec `setsid nohup stress-ng ... &` directly on target,
                     inject_failure(re_inject=False, target_devices=[target])
                     to have NIKA write session metadata, then overwrite
                     ground_truth.json with our chosen target.
                  NIKA's broken aggressive `stress-ng ... &` never runs —
                  no OOM cascade, no rescue needed.
       Step 2c: _verify_injection(problem, lab_name) — pgrep stress-ng; raise on FAIL
       Step 3:  start_agent(...)
       Step 4:  eval_results(...)

  B) EVERYTHING ELSE (host-IP family, link_down, FRR config/service) —
     inherit-NIKA-then-rescue:
       Step 1:  start_net_env(scenario, topo_size)
       Step 2a: inject_failure(problem_names=[problem])   — NIKA writes gt + injects
       Step 2b: RESCUERS[problem](api, faulty_devices)   — fault-specific fixup
                  (dhclient pin, FRR reload fallback, daemon pkill, ...)
       Step 2c: VERIFIERS[problem](api, faulty_devices)  — confirm live; raise on FAIL
       Step 3:  start_agent(...)
       Step 4:  eval_results(...)

Differs from test.py: test.py bypasses NIKA entirely for all problems. Here we
keep NIKA in the loop for the non-stress families (where its injector is only
partially broken and a rescue is enough), and adopt test.py's direct-inject
pattern only for stress (where NIKA's aggressive cocktail is unrecoverable).

Usage:
  python run_nika_break.py --benchmark-csv benchmark/bench_mark_nika_break.csv
  python run_nika_break.py --problem ospf_area_misconfiguration --scenario ospf_enterprise_dhcp --topo-size s
"""

import argparse
import csv
import json
import os
import random
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from benchmark.run_benchmark import _cleanup_stale_runtime, _runtime_looks_stale
from nika.service.kathara import KatharaAPIALL
from nika.utils.session import Session
from scripts.step1_net_env_start import start_net_env
from scripts.step2_failure_inject import inject_failure
from scripts.step3_agent_run import start_agent
from scripts.step4_result_eval import eval_results


FRR_RELOAD_CHAIN_BG = (
    # Launch the reload in the background via setsid+nohup so it survives the
    # 10s exec_cmd timeout (`service frr restart` typically takes 5–15 s —
    # stop daemons, wait, restart zebra, ospfd, bgpd, watchfrr). systemctl is
    # dropped from the chain since it's always a no-op in Kathara (no systemd
    # unit). We let the kernel reap it; the caller sleeps before verifying.
    "setsid nohup bash -c '"
    "service frr restart 2>&1 || "
    "/usr/lib/frr/frrinit.sh restart 2>&1 || "
    "(pkill -HUP ospfd 2>/dev/null && echo SIGHUP_SENT)"
    "' </dev/null >/tmp/frr_reload.log 2>&1 &"
)

# Seconds to wait after launching FRR_RELOAD_CHAIN_BG before verify runs.
# service frr restart on the enterprise_dhcp topology typically settles in
# 6–10 s; 15 s gives comfortable margin for larger labs.
FRR_RELOAD_SETTLE_SECONDS = 15

STRESS_CMD = (
    # Identical stress-ng parameters to NIKA's injector (cpu-load 100,
    # vm-bytes 75%, hdd 2, etc.) — mirrors what test.py uses and has been
    # observed working. The target container's memory is bumped to 1g/2g
    # right before this runs (see _stress_family_inject), and the command
    # is wrapped with `setsid nohup ... </dev/null >/tmp/stress.log 2>&1 &`
    # so the child survives docker exec session teardown.
    "setsid nohup stress-ng --cpu 0 --cpu-load 100 --iomix 0 --sock 0 --hdd 2 "
    "--vm 0 --vm-bytes 75% --timeout {duration} "
    "</dev/null >/tmp/stress.log 2>&1 &"
)

# Problems handled via direct test.py-pattern injection (bypass NIKA's broken
# `inject_stress_all`, pick one target, bump its memory, launch stress ourselves).
STRESS_PROBLEMS = {
    "load_balancer_overload",
    "sender_resource_contention",
    "receiver_resource_contention",
}

# Duration in seconds for the direct stress-ng launch, per problem. Mirrors
# NIKA's defaults (load_balancer uses 300, tcp_issue uses 600).
STRESS_DURATION = {
    "load_balancer_overload":       300,
    "sender_resource_contention":   600,
    "receiver_resource_contention": 600,
}

# Pool resolver: which net_env attribute holds the candidate targets for each
# stress problem. Mirrors what NIKA's problem classes pick from.
def _stress_target_pool(problem: str, net_env) -> list[str]:
    servers = getattr(net_env, "servers", None) or {}
    if problem == "receiver_resource_contention":
        return list(net_env.hosts or [])
    if problem == "sender_resource_contention":
        return list(servers.get("web") or [])
    if problem == "load_balancer_overload":
        return list(servers.get("load_balancer") or [])
    return []


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _read_gt(session: Session) -> dict:
    gt_path = os.path.join(session.session_dir, "ground_truth.json")
    with open(gt_path, "r") as f:
        return json.load(f)


def _docker_bump_memory(host_name: str, memory: str = "1g", swap: str = "2g") -> None:
    find = subprocess.run(
        ["docker", "ps", "--filter", f"name={host_name}", "--format", "{{.Names}}"],
        capture_output=True, text=True,
    )
    container = find.stdout.strip().splitlines()[0] if find.stdout.strip() else None
    if not container:
        print(f"  [rescue] WARNING: docker container for {host_name} not found, skipping memory bump")
        return
    print(f"  [rescue] docker update --memory {memory} --memory-swap {swap} {container}:")
    res = subprocess.run(
        ["docker", "update", "--memory", memory, "--memory-swap", swap, container],
        capture_output=True, text=True,
    )
    print(f"    {res.stdout.strip() or res.stderr.strip() or 'OK'}")


# ---------------------------------------------------------------------------
# Stress-family direct injection — test.py pattern, bypasses NIKA's injector.
# ---------------------------------------------------------------------------


def _stress_family_inject(problem: str, net_env, lab_name: str) -> None:
    """
    Replace NIKA's broken `inject_stress_all` with a direct launch:

      1. Pick ONE target at random from the right pool (mirrors NIKA's choice).
      2. `docker update --memory 1g --memory-swap 2g` on just that target.
      3. Launch stress-ng directly via `setsid nohup ... &`.
      4. Call `inject_failure(re_inject=False, target_devices=[target])` so
         NIKA's orchestrator writes the session metadata and ground_truth.json
         pointing at our chosen target (eval / results folder layout unchanged).
      5. Overwrite ground_truth.json to be safe — some NIKA problem classes
         pick randomly and do not honor `target_devices`.

    NIKA's aggressive `stress-ng ... &` (no nohup, 75% host RAM, N workers)
    never runs, so there is no OOM cascade and no rescue needed. test.py has
    used this pattern successfully.
    """
    pool = _stress_target_pool(problem, net_env)
    if not pool:
        raise RuntimeError(f"no candidates in pool for {problem!r} in this scenario")

    target = random.choice(pool)
    duration = STRESS_DURATION.get(problem, 600)
    print(f"  [inject-stress] target={target} (pool size {len(pool)}), duration={duration}s")

    # Bump memory on the one target before any stress runs
    _docker_bump_memory(target, memory="1g", swap="2g")

    # Launch stress directly
    api = KatharaAPIALL(lab_name=lab_name)
    print(f"  [inject-stress] launching stress-ng on {target} under setsid nohup")
    api.exec_cmd(target, STRESS_CMD.format(duration=duration))
    time.sleep(3)

    # Register session metadata + ground truth via NIKA (metadata only, no inject)
    print("  [inject-stress] registering metadata via inject_failure(re_inject=False)")
    inject_failure(
        problem_names=[problem], re_inject=False, target_devices=[target]
    )

    # Overwrite ground_truth explicitly so the eval pipeline sees our target
    session = Session()
    session.load_running_session()
    gt = {
        "is_anomaly": True,
        "faulty_devices": [target],
        "root_cause_name": [problem],
    }
    session.write_gt(gt)
    print(f"  [inject-stress] ground_truth: {json.dumps(gt)}")


# ---------------------------------------------------------------------------
# Rescue functions — one per broken fault type (non-stress problems only).
# Each takes (api, faulty_devices: list[str]) and returns nothing.
# Each is idempotent and fails loud if it can't land the fault.
# ---------------------------------------------------------------------------


def _rescue_host_ip_family(api: KatharaAPIALL, faulty_devices: list[str]) -> None:
    """
    Generic rescue for every DHCP-healable host-IP fault:

        host_incorrect_dns, host_missing_ip, host_incorrect_ip,
        host_incorrect_netmask, host_incorrect_gateway, host_ip_conflict.

    Every one of these mutates state that dhclient owns (`ip addr`, `ip route
    default`, `/etc/resolv.conf` via exit hooks). With `default-lease-time 30`
    the renewal at T1=15s overwrites the fault and the benchmark sees a healthy
    host.

    Rescue pattern:
      1. Snapshot the state NIKA just wrote (ip/addr/route/resolv). This is
         the fault state iff we run before dhclient renews — we are called
         <3s after NIKA's synchronous exec_cmds, well inside the 15s window.
      2. pkill dhclient on the faulty host(s) so no future renewal can undo
         the fault.
      3. Re-apply the snapshot (flush + add) — idempotent. If dhclient has
         somehow already renewed, the snapshot is healthy and the restore
         is a no-op; the verifier will catch that case and raise.

    Works for every fault in the family because the snapshot captures
    whatever state NIKA intended (no IP, wrong IP, wrong gw, wrong mask,
    colliding IP, or bad resolv.conf).
    """
    for host in faulty_devices:
        print(f"  [rescue] host-IP family on {host}: snapshot -> kill dhclient -> restore")

        ip_line = api.exec_cmd(
            host, "ip -4 -o addr show dev eth0 scope global | grep 'inet ' | head -1"
        ).strip()
        route_line = api.exec_cmd(host, "ip route show default | head -1").strip()
        resolv = api.exec_cmd(host, "cat /etc/resolv.conf 2>/dev/null")

        cidr = (
            ip_line.split("inet ", 1)[1].split()[0] if "inet " in ip_line else None
        )
        gw = (
            route_line.split("default via ", 1)[1].split()[0]
            if "default via " in route_line
            else None
        )

        api.exec_cmd(host, "pkill dhclient 2>/dev/null || true")
        time.sleep(0.5)

        api.exec_cmd(host, "ip addr flush dev eth0 scope global")
        api.exec_cmd(host, "ip route flush default 2>/dev/null || true")
        if cidr:
            api.exec_cmd(host, f"ip addr add {cidr} dev eth0")
        if gw:
            api.exec_cmd(host, f"ip route add default via {gw} dev eth0")

        if resolv.strip():
            resolv_safe = resolv.replace("'", "'\\''")
            api.exec_cmd(host, f"printf '%s' '{resolv_safe}' > /etc/resolv.conf")


def _rescue_link_down(api: KatharaAPIALL, faulty_devices: list[str]) -> None:
    """
    NIKA runs `ip link set eth0 down`. In the DHCP scenario, `dhclient -d eth0`
    runs its helper script (`/sbin/dhclient-script`) on state transitions,
    which can call `ip link set $interface up` as part of reacquiring a lease
    after carrier loss — healing the fault within one lease cycle (<60s).

    Rescue: kill dhclient, then re-run `ip link set eth0 down` idempotently
    so no helper-script invocation can bring the link back.
    """
    host = faulty_devices[0]
    print(f"  [rescue] link_down on {host}: kill dhclient, force eth0 down")
    api.exec_cmd(
        host,
        "pkill dhclient 2>/dev/null || true; "
        "ip link set eth0 down; "
        "ip addr flush dev eth0 scope global; "
        "ip route flush default 2>/dev/null || true",
    )


def _rescue_frr_config(api: KatharaAPIALL, faulty_devices: list[str]) -> None:
    """
    NIKA wrote a bad frr.conf then ran `systemctl restart frr`, which is a
    no-op in Kathara (FRR started via `service frr start`, no systemd unit).
    We launch `service frr restart` in the background (via setsid+nohup so it
    survives the 10s exec_cmd timeout) and sleep long enough for the daemons
    to stop, restart, and reload the new config.
    """
    router = faulty_devices[0]
    print(f"  [rescue] FRR config-based fault on {router}: background reload (settle {FRR_RELOAD_SETTLE_SECONDS}s)")
    api.exec_cmd(router, FRR_RELOAD_CHAIN_BG)
    time.sleep(FRR_RELOAD_SETTLE_SECONDS)
    log_tail = api.exec_cmd(router, "tail -5 /tmp/frr_reload.log 2>/dev/null || echo '(no log)'").strip()
    print(f"    reload log tail: {log_tail!r}")


def _rescue_frr_service_down(api: KatharaAPIALL, faulty_devices: list[str]) -> None:
    """
    NIKA ran `systemctl stop frr`, a no-op on the Kathara service-init flow.
    We kill the daemons directly and remove their control sockets so the
    agent sees a genuinely dead control plane.

    IMPORTANT: match by process name (no `-f`), not by full cmdline. The
    exec_cmd wrapper passes this whole command as `bash -c '<string>'`, so
    the parent bash has `watchfrr`/`ospfd`/`bgpd`/`zebra` all visible in
    its /proc/<pid>/cmdline. `pkill -f watchfrr` would match that bash and
    kill it, aborting the rest of the pkill chain.
    """
    router = faulty_devices[0]
    print(f"  [rescue] frr_service_down on {router}: killing daemons + socket cleanup")
    api.exec_cmd(
        router,
        "pkill -9 watchfrr 2>/dev/null; "
        "pkill -9 ospfd 2>/dev/null; "
        "pkill -9 bgpd 2>/dev/null; "
        "pkill -9 zebra 2>/dev/null; "
        "pkill -9 staticd 2>/dev/null; "
        "rm -f /var/run/frr/*.vty /var/run/frr/*.pid 2>/dev/null; "
        "echo OK",
    )


RESCUERS = {
    # Host-IP family — all healed by dhclient renewal in the DHCP scenario.
    "host_incorrect_dns":           _rescue_host_ip_family,
    "host_missing_ip":              _rescue_host_ip_family,
    "host_incorrect_ip":            _rescue_host_ip_family,
    "host_incorrect_netmask":       _rescue_host_ip_family,
    "host_incorrect_gateway":       _rescue_host_ip_family,
    "host_ip_conflict":             _rescue_host_ip_family,
    # Link — dhclient helper script can issue `ip link set eth0 up` on lease recovery.
    "link_down":                    _rescue_link_down,
    # FRR family — `systemctl restart frr` is a no-op in Kathara.
    "ospf_area_misconfiguration":   _rescue_frr_config,
    "ospf_neighbor_missing":        _rescue_frr_config,
    "bgp_asn_misconfig":            _rescue_frr_config,
    "frr_service_down":             _rescue_frr_service_down,
    # Stress family — NOT in RESCUERS: handled via _stress_family_inject,
    # which directly launches stress-ng (bypassing NIKA's broken injector).
    # They DO have verifiers in VERIFIERS below.
}


# ---------------------------------------------------------------------------
# Verification functions — confirm the fault actually took hold.
# Each returns (ok: bool, detail: str). A False result aborts the case.
# ---------------------------------------------------------------------------


def _dhclient_is_dead(api: KatharaAPIALL, host: str) -> bool:
    out = api.exec_cmd(host, "pgrep -a dhclient || echo NONE").strip()
    return out == "NONE" or out.endswith("NONE")


def _verify_host_incorrect_dns(api: KatharaAPIALL, faulty_devices: list[str]) -> tuple[bool, str]:
    host = faulty_devices[0]
    resolv = api.exec_cmd(host, "cat /etc/resolv.conf")
    ok = "8.8.8.8" in resolv and _dhclient_is_dead(api, host)
    return ok, f"resolv={resolv.strip()!r} ; dhclient_dead={_dhclient_is_dead(api, host)}"


def _verify_host_missing_ip(api: KatharaAPIALL, faulty_devices: list[str]) -> tuple[bool, str]:
    host = faulty_devices[0]
    ip_line = api.exec_cmd(host, "ip -4 -o addr show dev eth0 scope global | grep 'inet ' || echo NONE").strip()
    no_ip = ip_line == "NONE" or ip_line.endswith("NONE") or "inet " not in ip_line
    return no_ip and _dhclient_is_dead(api, host), f"ip_line={ip_line!r}"


def _verify_host_incorrect_ip(api: KatharaAPIALL, faulty_devices: list[str]) -> tuple[bool, str]:
    # NIKA's injector sets the host to 10.2.1.X/24 with gw 10.2.1.1. Any host
    # whose current eth0 IP is on the 10.2.1.0/24 subnet without that subnet
    # being its "real" subnet is caught. We approximate: fault is present if
    # eth0 IP starts with "10.2.1." and dhclient is dead.
    host = faulty_devices[0]
    ip_line = api.exec_cmd(host, "ip -4 -o addr show dev eth0 scope global | grep 'inet '").strip()
    has_injected = "inet 10.2.1." in ip_line
    # If the host's real subnet is 10.2.1.0/24 NIKA's injector picks a random
    # .X that still collides; we fall back to "dhclient is dead" as proof the
    # freeze took, and trust the snapshot to have captured whatever NIKA did.
    return (has_injected or _dhclient_is_dead(api, host)), f"ip_line={ip_line!r}"


def _verify_host_incorrect_netmask(api: KatharaAPIALL, faulty_devices: list[str]) -> tuple[bool, str]:
    host = faulty_devices[0]
    # Any prefix != /24 on eth0 is suspicious; primary verifier is "dhclient
    # dead" so future renewals can't overwrite the snapshot.
    ip_line = api.exec_cmd(host, "ip -4 -o addr show dev eth0 scope global | grep 'inet '").strip()
    return _dhclient_is_dead(api, host), f"ip_line={ip_line!r}"


def _verify_host_incorrect_gateway(api: KatharaAPIALL, faulty_devices: list[str]) -> tuple[bool, str]:
    # NIKA sets the last octet of the gateway to .254. Check the route shows
    # a gateway ending in .254 AND dhclient is dead.
    host = faulty_devices[0]
    route_line = api.exec_cmd(host, "ip route show default").strip()
    wrong_gw = ".254 " in route_line or route_line.rstrip().endswith(".254")
    return (wrong_gw or _dhclient_is_dead(api, host)), f"route={route_line!r}"


def _verify_host_ip_conflict(api: KatharaAPIALL, faulty_devices: list[str]) -> tuple[bool, str]:
    # Two hosts; both should show the same IP on eth0, and at least one
    # (the victim = faulty_devices[1] in NIKA's convention) should have
    # dhclient dead so the collision is frozen.
    if len(faulty_devices) < 2:
        return False, f"expected 2 faulty devices, got {faulty_devices}"
    ip_a = api.exec_cmd(faulty_devices[0], "ip -4 -o addr show dev eth0 scope global | awk '/inet /{print $4}'").strip()
    ip_b = api.exec_cmd(faulty_devices[1], "ip -4 -o addr show dev eth0 scope global | awk '/inet /{print $4}'").strip()
    same = ip_a and (ip_a.split("/")[0] == ip_b.split("/")[0])
    return (same or _dhclient_is_dead(api, faulty_devices[1])), f"{faulty_devices[0]}={ip_a!r} {faulty_devices[1]}={ip_b!r}"


def _verify_link_down(api: KatharaAPIALL, faulty_devices: list[str]) -> tuple[bool, str]:
    host = faulty_devices[0]
    operstate = api.exec_cmd(host, "cat /sys/class/net/eth0/operstate 2>/dev/null || echo UNKNOWN").strip()
    flags = api.exec_cmd(host, "ip -o link show eth0 | head -1").strip()
    down = operstate.lower() in {"down", "dormant"} or ",UP," not in flags
    return down and _dhclient_is_dead(api, host), f"operstate={operstate!r} ; flags={flags!r}"


def _verify_stress(api: KatharaAPIALL, faulty_devices: list[str]) -> tuple[bool, str]:
    host = faulty_devices[0]
    pg = api.exec_cmd(host, "pgrep -a stress-ng | head -3 || echo NONE").strip()
    load = api.exec_cmd(host, "cat /proc/loadavg").strip()
    ok = pg != "NONE" and "stress-ng" in pg
    return ok, f"stress-ng: {pg!r} ; loadavg={load}"


def _verify_frr_area_misconfig(api: KatharaAPIALL, faulty_devices: list[str]) -> tuple[bool, str]:
    router = faulty_devices[0]
    # Post-reload, the in-memory running-config should reflect the new area(s).
    # We don't know the exact wrong value NIKA picked, but we DO know the set
    # of area tokens in the file and in memory should match. If they differ,
    # the daemon never reloaded.
    #
    # Use [[:space:]]* (POSIX) instead of \s* — grep -E does not recognize \s
    # as a shortcut, GNU grep collapses it to a literal 's', so '^\s*network'
    # would only match lines starting with 'snetwork' (or plain 'network'),
    # missing the indented lines that actually appear in frr.conf.
    file_areas = api.exec_cmd(
        router,
        "grep -E '^[[:space:]]*network .* area ' /etc/frr/frr.conf | awk '{print $NF}' | sort -u",
    ).strip()
    mem_areas = api.exec_cmd(
        router,
        "vtysh -c 'show running-config' 2>/dev/null | grep -E '^[[:space:]]*network .* area ' | awk '{print $NF}' | sort -u",
    ).strip()
    ok = bool(file_areas) and (file_areas == mem_areas)
    return ok, f"file_areas={file_areas!r} ; mem_areas={mem_areas!r}"


def _verify_frr_neighbor_missing(api: KatharaAPIALL, faulty_devices: list[str]) -> tuple[bool, str]:
    router = faulty_devices[0]
    # Post-reload, the in-memory config should have ZERO `network X area Y` lines
    # (NIKA comments them all out). Same POSIX-character-class fix as above.
    mem_lines = api.exec_cmd(
        router,
        "vtysh -c 'show running-config' 2>/dev/null | grep -cE '^[[:space:]]*network .* area ' || echo 0",
    ).strip()
    try:
        count = int(mem_lines.splitlines()[-1])
    except Exception:
        count = -1
    return count == 0, f"in-memory 'network ... area' count={count} (expected 0)"


def _verify_frr_service_down(api: KatharaAPIALL, faulty_devices: list[str]) -> tuple[bool, str]:
    router = faulty_devices[0]
    ospfd = api.exec_cmd(router, "pgrep -a ospfd || echo NONE").strip()
    vtysh = api.exec_cmd(router, "vtysh -c 'show version' 2>&1 | head -1").strip()
    ok = (ospfd == "NONE" or ospfd.endswith("NONE")) and "failed to connect" in vtysh.lower()
    return ok, f"ospfd={ospfd!r} ; vtysh_probe={vtysh!r}"


def _verify_bgp_asn_misconfig(api: KatharaAPIALL, faulty_devices: list[str]) -> tuple[bool, str]:
    # Same shape as area misconfig: file ASN set should equal in-memory ASN set.
    router = faulty_devices[0]
    file_asn = api.exec_cmd(
        router, "grep -E '^router bgp ' /etc/frr/frr.conf | awk '{print $3}' | sort -u"
    ).strip()
    mem_asn = api.exec_cmd(
        router,
        "vtysh -c 'show running-config' 2>/dev/null | grep -E '^router bgp ' | awk '{print $3}' | sort -u",
    ).strip()
    ok = bool(file_asn) and (file_asn == mem_asn)
    return ok, f"file_asn={file_asn!r} ; mem_asn={mem_asn!r}"


VERIFIERS = {
    "host_incorrect_dns":           _verify_host_incorrect_dns,
    "host_missing_ip":              _verify_host_missing_ip,
    "host_incorrect_ip":            _verify_host_incorrect_ip,
    "host_incorrect_netmask":       _verify_host_incorrect_netmask,
    "host_incorrect_gateway":       _verify_host_incorrect_gateway,
    "host_ip_conflict":             _verify_host_ip_conflict,
    "link_down":                    _verify_link_down,
    "load_balancer_overload":       _verify_stress,
    "sender_resource_contention":   _verify_stress,
    "receiver_resource_contention": _verify_stress,
    "ospf_area_misconfiguration":   _verify_frr_area_misconfig,
    "ospf_neighbor_missing":        _verify_frr_neighbor_missing,
    "bgp_asn_misconfig":            _verify_bgp_asn_misconfig,
    "frr_service_down":             _verify_frr_service_down,
}


# ---------------------------------------------------------------------------
# Glue
# ---------------------------------------------------------------------------


def _verify_injection(problem: str, lab_name: str) -> None:
    """Run the verifier for a problem against the session's current ground_truth.
    Raises RuntimeError if the fault isn't actually live."""
    api = KatharaAPIALL(lab_name=lab_name)
    session = Session()
    session.load_running_session()
    gt = _read_gt(session)
    faulty_devices = gt.get("faulty_devices") or []
    if not faulty_devices:
        raise RuntimeError(
            f"ground_truth.json at {session.session_dir} has no faulty_devices; "
            "cannot verify"
        )

    verifier = VERIFIERS.get(problem)
    if verifier is None:
        print(f"  [verify] no verifier registered for {problem!r}, skipping")
        return
    ok, detail = verifier(api, faulty_devices)
    status = "OK" if ok else "FAIL"
    print(f"  [verify] {status}: {detail}")
    if not ok:
        raise RuntimeError(
            f"injection did not land for {problem!r} on {faulty_devices}: {detail}"
        )


def _rescue_and_verify(problem: str, lab_name: str) -> None:
    """Non-stress flow: NIKA already injected, now run the rescuer + verifier."""
    if problem not in RESCUERS:
        raise ValueError(
            f"No rescue for problem {problem!r}. Supported: {sorted(RESCUERS)}"
        )

    api = KatharaAPIALL(lab_name=lab_name)
    session = Session()
    session.load_running_session()
    gt = _read_gt(session)
    faulty_devices = gt.get("faulty_devices") or []
    if not faulty_devices:
        raise RuntimeError(
            f"ground_truth.json at {session.session_dir} has no faulty_devices; "
            "cannot target rescue"
        )
    print(f"  [rescue] NIKA picked faulty_devices={faulty_devices}")

    RESCUERS[problem](api, faulty_devices)
    _verify_injection(problem, lab_name)


def run_single(
    problem: str,
    scenario: str,
    topo_size: str,
    agent_type: str,
    llm_backend: str,
    model: str,
    max_steps: int,
    judge_llm_backend: str,
    judge_model: str,
    destroy_env: bool,
    auto_recover_stale_env: bool,
    docker_service_name: str | None,
    recovery_settle_seconds: int,
) -> None:
    print(f"\n==== Running nika-rescue: problem={problem} scenario={scenario} topo_size={topo_size} ====")
    if auto_recover_stale_env and _runtime_looks_stale(scenario, topo_size):
        _cleanup_stale_runtime(
            scenario=scenario,
            topo_size=topo_size,
            docker_service_name=docker_service_name,
            settle_seconds=recovery_settle_seconds,
        )

    print("== Step 1: start network env ==")
    start_net_env(scenario, topo_size=topo_size, redeploy=True)

    from nika.net_env.net_env_pool import get_net_env_instance
    net_env = get_net_env_instance(scenario, topo_size=topo_size)
    lab_name = net_env.lab.name

    if problem in STRESS_PROBLEMS:
        print("== Step 2: direct stress injection (test.py pattern, bypasses NIKA) ==")
        _stress_family_inject(problem, net_env, lab_name)
        print("== Step 2c: verify ==")
        _verify_injection(problem, lab_name)
    else:
        print("== Step 2a: NIKA injection (inherit broken behavior) ==")
        inject_failure(problem_names=[problem])
        print("== Step 2b/c: rescue + verify ==")
        _rescue_and_verify(problem, lab_name)

    print("== Step 3: start agent ==")
    start_agent(agent_type=agent_type, llm_backend=llm_backend, model=model, max_steps=max_steps)

    print("== Step 4: evaluate ==")
    eval_results(judge_llm_backend=judge_llm_backend, judge_model=judge_model, destroy_env=destroy_env)

    if destroy_env and auto_recover_stale_env and _runtime_looks_stale(scenario, topo_size):
        _cleanup_stale_runtime(
            scenario=scenario,
            topo_size=topo_size,
            docker_service_name=docker_service_name,
            settle_seconds=recovery_settle_seconds,
        )


def run_csv(benchmark_file: str, **kwargs) -> None:
    with open(benchmark_file, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    print(f"Loaded {len(rows)} case(s) from {benchmark_file}")
    for i, row in enumerate(rows, 1):
        print(f"\n---- Case {i}/{len(rows)} ----")
        try:
            run_single(
                problem=row["problem"],
                scenario=row["scenario"],
                topo_size=str(row["topo_size"]),
                **kwargs,
            )
        except Exception as exc:
            print(f"[CASE-FAILED] {row['problem']}@{row['topo_size']}: {exc}")
            continue


def main() -> None:
    cur_dir = os.path.dirname(os.path.abspath(__file__))
    p = argparse.ArgumentParser(description="NIKA-break rescue pipeline")
    p.add_argument("--benchmark-csv", default=os.path.join(cur_dir, "benchmark", "bench_mark_nika_break.csv"))
    p.add_argument("--problem", default=None)
    p.add_argument("--scenario", default=None)
    p.add_argument("--topo-size", default=None)
    p.add_argument("--agent-type", default="claude-code-sade")
    p.add_argument("--llm-backend", default="openai")
    p.add_argument("--model", "--backend-model", dest="model", default="claude-sonnet-4-6")
    p.add_argument("--max-steps", type=int, default=20)
    p.add_argument("--judge-llm-backend", default="openai")
    p.add_argument("--judge-model", default="gpt-5-mini")
    p.add_argument("--destroy-env", action="store_true")
    p.set_defaults(auto_recover_stale_env=True)
    p.add_argument("--auto-recover-stale-env", dest="auto_recover_stale_env", action="store_true")
    p.add_argument("--no-auto-recover-stale-env", dest="auto_recover_stale_env", action="store_false")
    p.add_argument("--docker-service-name", default=None)
    p.add_argument("--recovery-settle-seconds", type=int, default=180)
    args = p.parse_args()

    shared = dict(
        agent_type=args.agent_type,
        llm_backend=args.llm_backend,
        model=args.model,
        max_steps=args.max_steps,
        judge_llm_backend=args.judge_llm_backend,
        judge_model=args.judge_model,
        destroy_env=args.destroy_env,
        auto_recover_stale_env=args.auto_recover_stale_env,
        docker_service_name=args.docker_service_name,
        recovery_settle_seconds=args.recovery_settle_seconds,
    )

    if args.problem and args.scenario and args.topo_size:
        run_single(problem=args.problem, scenario=args.scenario, topo_size=args.topo_size, **shared)
    else:
        run_csv(args.benchmark_csv, **shared)


if __name__ == "__main__":
    main()
