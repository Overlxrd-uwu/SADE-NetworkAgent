---
name: diagnosis-methodology-skill
description: Broad-search escalation toolbox. Enter when the blind start surfaces no symptom. Run phases in order, and exit the moment a helper surfaces an anomaly.
---

# Diagnosis Methodology

## When to enter
Enter only when reachability is clean and no fault is already implicated. Your first action inside this skill is Phase A. If any helper surfaces an anomaly, leave broad search and pivot to symptom-first diagnosis with that anomaly as the active lead.

## How to run a helper
```
python ../../h.py <script> [args]   # cwd is already src/agent/; h.py lives two levels up at the project root. A bare `python ../../h.py` lists the available scripts.
```
Run that command exactly — no `cd` prefix, no `/mnt/c/...` WSL path, no absolute Windows path. The shell is Git-Bash (drives appear as `/c/...`, not `/mnt/c/...`), and rewrites to absolute paths frequently land on a stale tree. If a `python ../../h.py` invocation errors with a path or import failure, do not rewrite the launcher path; verify cwd with `pwd` and report the discrepancy.

Default text mode auto-shows only flagged rows and stays compact on l-size topologies. Use `--json` only for targeted queries on small data; on broad sweeps it exceeds the inline token budget. Every helper accepts `--help`; do not read its source to discover flags.

Base MCP node-local tools use `host_name` even for routers, servers, load balancers, and witnesses; FRR MCP tools use `router_name`; helper scripts often use `--device`. Do not mix these schemas.

## Principles
- Each phase pairs a **triage helper** (broad, run first) with **specialists** (narrow, run only once triage indicates them). Running a specialist ahead of its triage squanders turns.
- A helper flag is evidence, not proof. Consult `baseline-behavior-skill` before calling it a symptom, and confirm locally before naming a faulty device.
- If broad search devolves into raw `exec_shell` fan-outs, a phase has been skipped — return to the appropriate helper.

## Phase A — L2 and infrastructure
Triage (run both, default scope, no `--group`):
- [infra_sweep](./scripts/infra_sweep.py): nftables, addressing, routing, ARP, resolver, and link statistics across every device in a single pass.
- [l2_snapshot](./scripts/l2_snapshot.py): duplicate `link/ether` detection across the lab. `infra_sweep` does not perform duplicate-MAC detection; without this, a `mac_address_conflict` manifests only as generic per-host anomalies.
Phase A is incomplete until both triage helpers have run and been examined; a clean `infra_sweep` does not clear L2 identity faults.

Specialist: [network_inventory](./scripts/network_inventory.py) — topology overview when the task description omits one.

## Phase B — Control plane and routing
Triage depends on the topology:
- OSPF/FRR: [ospf_snapshot](./scripts/ospf_snapshot.py) for FRR health, adjacency, per-interface OSPF state, and area consistency.
- BGP/FRR: [bgp_snapshot](../bgp-fault-skill/scripts/bgp_snapshot.py) for FRR/BGP process, ASN, neighbor, advertisement, and blackhole evidence.
- Static, RIP, SDN, or P4: use `network_inventory`, `safe_reachability`, routing-table/controller checks, and targeted daemon probes appropriate to the topology.

Always run [tc_snapshot](./scripts/tc_snapshot.py) when the symptom could be throughput, corruption, jitter, or qdisc shaping.

**Guardrail.** If Phase B reports the fabric healthy but Phase C or D is still broken, verify each implicated router's daemon directly (`systemctl is-active <daemon>`, `pgrep -a <daemon>`) before concluding `is_anomaly=False`.

## Phase C — Host-local (enter only after Phase A implicates a host)
Specialists: [host_path_snapshot](./scripts/host_path_snapshot.py) (`ip route get <target>` with next-hop neighbor state) · [dhcp_link_history](./scripts/dhcp_link_history.py) (temporal flap and recovery history) · [safe_reachability](./scripts/safe_reachability.py) (fallback for MCP reachability failure).

## Phase D — Service, resolution, and resource pressure
Triage: [service_snapshot](./scripts/service_snapshot.py) (combined DNS + HTTP + localhost HTTP + service-process, auto-compacting) · [pressure_sweep](./scripts/pressure_sweep.py) (stress-tool detection, CPU, socket counts, daemon presence).
Specialists: [dns_client_snapshot](./scripts/dns_client_snapshot.py) (majority-minority resolver outlier and per-host per-name lookup detail) · [http_client_snapshot](./scripts/http_client_snapshot.py) (per-host curl timing breakdown).

## Before submitting `is_anomaly=False`
The Phase A, Phase B, and Phase D triage helpers must each have produced output that was examined. A brief Phase D is acceptable; skipping it is not.

## Exit
Once a device, path, or service owner is implicated, leave this skill and enter the matching fault-family skill from `CLAUDE.md`.
