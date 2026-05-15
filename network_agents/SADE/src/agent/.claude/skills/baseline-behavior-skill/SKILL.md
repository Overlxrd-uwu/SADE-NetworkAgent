---
name: baseline-behavior-skill
description: Reference list of signals that look suspicious but are normal testbed behavior. Consult before promoting any observation to a symptom.
---

# Normal Behavior

## How To Use This Skill

- This skill is an **allowlist** of signals that are normal Kathara behavior and can therefore be dismissed as false positives.
- **Absence from this list does NOT mean a signal is normal.** If a helper flagged something and you cannot find a matching entry below, treat the flag as real evidence, not as "probably fine because it's small."
- Use it to avoid false positives, not to choose the troubleshooting order.
- A baseline note can weaken a theory, but it does not clear a directly implicated device by itself.
- A single follow-up probe (one ping, one curl) does NOT clear an intermittent symptom such as flapping link, transient drops, or `status=unknown` rows. Intermittent faults need either repeated probes over time or direct evidence on the device.

## Universal

- High `/proc/loadavg` can be host-shared, not container-local, because Kathara containers share the host kernel.
- `dmesg` is shared host kernel output. Do not use it as per-container evidence.
- Short DHCP leases are common in these labs and do not themselves indicate a fault.
- Brief DHCP instability during startup can self-recover.
- One clean service-layer check does not clear unresolved lower-layer faults.

## Routing And FRR

- `frr_show_running_config` and `frr_show_ip_route` can look healthy even if FRR is dead; check the daemon processes directly.
- FRR helper tools use `router_name`.
- If you are unsure of the FRR schema, use `exec_shell(host_name="<router>", command="vtysh -c '...'")`.
- Cached routes can keep ping working after OSPF or BGP breaks.

## Service And HTTP

- Healthy DNS or HTTP does not clear lower-layer faults (ACL, OSPF, L2 identity).
- Curl by IP exercises routing plus HTTP only; curl by hostname also exercises DNS.
- A timeout on a service port that has no listening server is expected; confirm the service actually runs before treating it as a fault.
