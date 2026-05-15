---
name: bgp-fault-skill
description: Identify BGP routing faults — ASN misconfiguration, missing route advertisement, prefix hijacking, blackhole route leak. Use when reachability failures follow BGP-routed paths, BGP sessions fail to establish, or expected prefixes are missing from peers.
---

# BGP Faults

## What These Faults Mean

- `bgp_asn_misconfig`: the router's local ASN does not match what its peers expect, so BGP sessions fail to establish.
- `bgp_missing_route_advertisement`: a `network` statement for a locally-attached prefix is missing from the router's `router bgp` block, so peers never learn that prefix.
- `bgp_hijacking`: a router loopback claims a service IP/prefix that belongs elsewhere, and BGP advertises it, so traffic is pulled to the wrong router.
- `bgp_blackhole_route_leak`: a static route to `Null0` is configured **inside FRR** *and* advertised into BGP via a matching `network` statement, attracting traffic that is then dropped.
- `host_static_blackhole`: a **kernel-level** blackhole route (`ip route ... blackhole`) is installed on a router for a directly-attached host subnet. There is no `ip route ... Null0` line in the FRR running-config; the prefix is the host's own subnet, which BGP already advertises as part of normal baseline config.

## Required tool usage

- FRR MCP tools use `router_name`, not `host_name`.
- If unsure of the FRR schema, fall back to `exec_shell(host_name="<router>", command="vtysh -c '...'")`.
- `frr_show_running_config` and `frr_show_ip_route` can look clean when the daemon is dead; they are secondary evidence.

## Guardrails

- A route being "missing or surprising" is not enough. You need direct config or routing-table evidence on the offending router.
- `bgp_hijacking` requires both the loopback IP AND the advertising `network` statement — one alone is not a hijack.
- `bgp_blackhole_route_leak` requires **both** an FRR-config `ip route <P> Null0` line **and** a matching `network <P>` advertisement under `router bgp`. A pre-existing `network` for a router's normal attached subnet is not enough on its own.
- `host_static_blackhole` requires a kernel-level `blackhole` route on the router for an attached host subnet, with **no** corresponding `ip route ... Null0` line in the FRR running-config. If you see a kernel blackhole and immediately conclude `bgp_blackhole_route_leak` because the prefix also appears as a `network` statement, you have misclassified — the `network` statement is normal baseline config; the leak label requires the explicit FRR-config Null0 line.
