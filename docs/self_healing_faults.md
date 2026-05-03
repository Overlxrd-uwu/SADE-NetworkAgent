# NIKA Benchmark Infrastructure Issues

## Overview

During iterative optimization of the SADE diagnostic agent we identified two distinct classes of NIKA-side issues that prevent the agent from being scored fairly. Both are benchmark infrastructure problems, not agent capability gaps.

1. **Self-healing or silent-failure fault injections** — the injection runs but leaves no observable trace at diagnosis time, either because environment automation reverses it or because the injector code targets a resource that doesn't exist on the chosen device.
2. **Always-on lab baseline misconfigurations** — the lab generator itself ships with a configuration that produces fault-shaped symptoms on every run of the affected scenario, regardless of what (if anything) is being injected. These pollute the symptom space and can mislead an agent toward a plausible-but-irrelevant diagnosis.

The original scope of this document was the `ospf_enterprise_dhcp` scenario; later additions cover `dc_clos_service` size `l`.

## Affected Fault Types

### 1. `host_incorrect_dns` (deterministic, always self-heals)

**Injection mechanism** (`injector_host.py`):
```python
exec_cmd(host_name, "echo 'nameserver 8.8.8.8' > /etc/resolv.conf")
```

**Healing mechanism** (`lab_dhcp.py`):
- All hosts run `dhclient -d eth0` in daemon mode
- DHCP lease configuration: `default-lease-time 30; max-lease-time 60;`
- On every lease renewal (~30s), dhclient overwrites `/etc/resolv.conf` with the correct nameserver from the DHCP option

**Observable window**: <30 seconds after injection. By the time the SADE agent completes Steps 0a-0c and reaches DNS checks (~60-90s), the resolv.conf has been restored.

**Evidence at diagnosis time**: None. `cat /etc/resolv.conf` shows correct `nameserver 10.200.0.2`.

**Reproducibility**: 100% self-healing across all topology sizes (s, m, l confirmed).

### 2. `dns_record_error` on `dc_clos_service` size `l` (silent injection failure, ~75% of runs)

This is a different class than self-healing: the NIKA injector runs but writes to a non-existent file, so no fault is ever present on the box. Documented here because it has the same end-result for the agent — no observable evidence at diagnosis time.

**Injection mechanism** (`src/nika/orchestrator/problems/end_host_failure/dns.py:32-55`):
```python
self.faulty_devices = [self.net_env.servers["dns"][0]]   # always dns_pod0
url = random.choice(self.net_env.web_urls)               # any pod's URL
self.target_website = url.split(".")[0]                  # e.g. "web4"
self.target_domain  = url.split(".")[1]                  # e.g. "pod3"
...
exec_cmd(faulty_devices[0],
    f"sed -i 's/.../.../' /etc/bind/db.{target_domain}") # sed db.pod3 on dns_pod0
exec_cmd(faulty_devices[0], "systemctl restart named")
```

**Why nothing lands on size `l`**:
- `faulty_devices` is hardcoded to `servers["dns"][0]` (always `dns_pod0`), but `target_domain` comes from a uniform `random.choice` across all 4 pods' URLs (`lab_services.py:441-444`).
- `dns_pod0`'s `/etc/bind/named.conf` only loads `zone "pod0"`. Files for other pods (`db.pod1`, `db.pod2`, `db.pod3`) do not exist on `dns_pod0`.
- When the random pick lands outside pod0 (3-in-4 chance at size `l`), `sed -i ... /etc/bind/db.podN` runs on a non-existent file and silently no-ops.
- `systemctl restart named` is also a no-op in Kathara containers (no systemd).

**Why size `s` and `m` mostly pass**:

| Size | super_spine_count → pods | URLs in pool | P(injection lands) |
|---|---|---|---|
| s | 1 | pod0 only | 100% — random pick is forced to pod0 |
| m | 2 | pod0 + pod1 | ~50% — coin flip |
| l | 4 | pod0..pod3 | ~25% — usually misses |

**Observable window**: None on the ~75% of size `l` runs that miss. `dns_pod0`'s zone file (`/etc/bind/db.pod0`) and `named.conf` are byte-for-byte identical to the clean lab.

**Compounding lab issue (size `l` only)**: `lab_services.py:365-370` writes one `nameserver` line per DNS server in the lab, so size `l` clients get 4 nameservers. glibc's `MAXNS=3` (compile-time constant in `<resolv.h>`) silently drops the 4th, so `dns_pod3` is never queried via `getaddrinfo`. Every `web*.pod3` URL fails to resolve from any client regardless of injection state. This baseline failure shape mimics a server-side DNS fault and tends to lure agents into a `host_incorrect_dns` or `dns-fault-skill` path.

**No verifier registered**: `run_nika_break.py:500-514` has no entry for `dns_record_error` in `VERIFIERS`, so `_verify_injection` (line 538-540) skips the check and returns. Silent injection failures are not caught.

**Evidence at diagnosis time** (run `0426175948`, picked `web4.pod3`):
- `cat /etc/bind/db.pod0` on dns_pod0 → all records correct, untouched
- `cat /etc/bind/named.conf` on dns_pod0 → only `pod0` zone loaded
- `dig web4.pod3 @10.0.0.2` → REFUSED (dns_pod0 has no pod3 zone, never had)
- `dig web4.pod3 @10.3.0.2` → 10.3.5.2 correct
- All four `dns_pod*` healthy, named running, port 53 listening, zone files clean

**Reproducibility**: Deterministic given the random seed. ~75% of size `l` runs leave no observable trace; the remaining ~25% (when `random.choice` lands on a pod0 URL) inject correctly. Sizes `s` and `m` are not affected by this specific failure mode (size `s`: always lands; size `m`: ~50% of runs miss).

### 3. `load_balancer_overload` (non-deterministic, intermittently self-heals)

**Injection mechanism** (`injector_host.py`):
```python
exec_cmd(host_name,
    "stress-ng --cpu 0 --cpu-load 100 --iomix 0 --sock 0 --hdd 2 "
    "-vm 0 --vm-bytes 75% --timeout 300 &")
```

**Healing mechanism** (Linux OOM killer):
- `--vm-bytes 75%` attempts to allocate 75% of **host** memory (shared across all Kathara containers)
- Under memory pressure (especially on larger topologies with more containers), the kernel OOM-killer terminates stress-ng workers
- All child processes are killed; parent may also be killed

**Observable window**: Variable. When stress-ng survives:
- Commands on load_balancer time out (>10s)
- `/proc/loadavg` shows 50-200+
- Agent can diagnose correctly

When stress-ng is OOM-killed:
- `ps aux` shows no stress-ng process
- Curl response times are normal (~850ms)
- `/proc/loadavg` is normal
- No residual evidence exists

**Note on `dmesg`**: In Kathara (Docker-based), `dmesg` shows the host kernel's ring buffer, shared across ALL containers. OOM-kill messages from any container or previous experiment appear in every container. This makes `dmesg` unreliable as container-specific evidence and can cause false positives (e.g., misdiagnosing `sender_application_delay` as `sender_resource_contention`).

**Reproducibility**: Non-deterministic. Observed passing on /s and /m in some runs, failing on /m and /l in others. Larger topologies (more containers, more memory pressure) are more likely to trigger OOM-kill.

## Impact on Evaluation

| Fault | Topology sizes | Loss mechanism | Loss rate | Agent accuracy ceiling |
|-------|---------------|----------------|-----------|----------------------|
| `host_incorrect_dns` | all (s, m, l) | dhclient overwrites injection | 100% | 0% (undiagnosable) |
| `dns_record_error` (`dc_clos_service`) | l (m partial) | injector sed targets non-existent file | ~75% on size `l`, ~50% on size `m`, 0% on size `s` | 0-25% on size `l` (only when random pick lands on pod0) |
| `load_balancer_overload` | varies by run | OOM-killer terminates stress-ng | ~30-50% (estimated) | ~50-70% across runs |

## Lab Baseline Issues (always-on, not fault-specific)

These are not fault injections — they are pre-existing misconfigurations baked into the lab generator. They produce symptoms that look like injected faults and are present on every run of the affected scenario, regardless of which fault (if any) is being injected.

### `dc_clos_service` size `l`: pod3 services unreachable by name from any client

**Mechanism** (`src/nika/net_env/data_center_routing/dc_clos_bgp/lab_services.py:365-370`):
```python
for host in tot_clients:
    ns_add_cmd = ""
    for dns in tot_dns:                    # iterates over ALL DNS servers in the lab
        ns_add_cmd += f"nameserver {dns.ip_address}\n"
    host.machine.create_file_from_string(ns_add_cmd, "/etc/resolv.conf")
```

The lab generator writes one `nameserver` line per DNS server in the topology. The DNS server count equals the pod count (= `super_spine_count`):

| Size | pods | nameservers per client | Within glibc `MAXNS=3`? |
|---|---|---|---|
| s | 1 | 1 | ✅ fine |
| m | 2 | 2 | ✅ fine |
| l | 4 | 4 | ❌ glibc silently drops the 4th |

**Conflict with glibc**: `MAXNS` is a compile-time constant in `<resolv.h>` (`#define MAXNS 3`) baked into every Linux container's libc. The 4th `nameserver` line in `/etc/resolv.conf` is silently ignored by `getaddrinfo` and friends.

**On size `l` specifically**: the 4th entry is `dns_pod3` (10.3.0.2). It is never queried by any client. None of the first three (`dns_pod0`, `dns_pod1`, `dns_pod2`) are authoritative for the `pod3` zone, so they all return REFUSED for any `web*.pod3` lookup. The system resolver gives up.

**Important — pod3 is not shut down**:
- All `webserver*_pod3` containers are up and serving HTTP locally (`service_snapshot` shows `Localhost HTTP: codes=200` for every pod3 web server).
- `get_reachability` shows 0% loss on direct-IP probes to pod3 hosts (e.g., `client_0` → `webserver3_pod3` at `10.3.4.2` returns `loss_percent: 0.0`, `status: ok`).
- `dns_pod3` itself is healthy: named running, port 53 listening, zone `pod3` correctly loaded with all `web0..web6` records.
- Direct query bypassing the system resolver works: `nslookup web0.pod3 10.3.0.2` → `10.3.1.2` ✓.

The break is **only** in the client → name → IP path, and only because libc never sends the query to `dns_pod3`. L3, BGP, named, and the web servers are all fine.

**Symptom shape this produces every run on size `l`**:
- All `curl http://web*.pod3/` from any client → `000` (`getaddrinfo` failure)
- `service_snapshot` HTTP table shows `problem:http_non_ok` for all 7 pod3 URLs across all 4 clients
- `service_snapshot` DNS table shows `no_addresses` for pod3 names (and, due to a separate `nslookup` interaction with `recursion no`, also for pod0 and pod1 names — see `dns_record_error` section above)
- `dig web*.pod3 +short` from any client returns empty (dig only queries the first nameserver, which is REFUSED)

**Why this matters for evaluation**: This baseline failure is identical in shape to a `host_incorrect_dns` fault on all 4 clients. Any agent reasoning from observed symptoms on size `l` will plausibly land on `host_incorrect_dns` regardless of what fault was actually injected — including when no fault was injected (e.g., when the `dns_record_error` injector silently no-op'd as described above). It also means runs that injected a *different* fault on size `l` may be polluted by this constant noise.

**Reproducibility**: 100% deterministic on every `dc_clos_service` size `l` run. Drop a freshly deployed lab with no injection, run `curl http://web0.pod3/` from any client → returns `000`.

## Recommendation

These cases should be:
1. **Reported separately** from standard agent accuracy metrics, with explanation. Runs where the injection demonstrably never landed (or healed before any probe could fire) cannot be used to score agent reasoning.
2. **Characterized as a benchmark design finding** — the fault injection does not guarantee a persistent observable state. The agent is being asked to find a fault that, on inspection of the live container, is not present.
3. Used as motivation for **fault injection robustness improvements** in future NIKA versions. The general pattern: injectors that mutate device-specific files should verify (a) the device they target actually owns the resource being mutated, (b) the resource exists before the mutation runs, and (c) the mutation persists past any environment-side restoration loop. None of these guarantees hold in the three cases above.

These are upstream NIKA / lab-generation issues, not SADE agent issues. An agent that correctly inspects the live state of `dns_pod0` in run `0426175948` will report that `dns_pod0` is healthy — which is true on the box, even though the ground-truth label says otherwise.
