---
name: host-ip-skill
description: Identify per-host L2/L3 identity faults — IP conflict, wrong IP, wrong gateway, wrong netmask, missing IP, host-local resolv.conf misconfig, static `arp -s` poisoning. Use when one host (or a small minority) shows an addressing anomaly its same-subnet peers do not share.
---

# Host IP Faults

## Rule out link first

Transient or intermittent host-identity symptoms — short lease, lost default route, missing IP, conflicting interface-state readings between probes — frequently originate from an unstable access link, not from host configuration. Confirm the access interface is present and stable before classifying anything in this family. If the interface is currently DOWN or missing, or is actively flapping, the case belongs to `link-fault-skill`, not here.

A low carrier-changes counter alone is not a link fault — startup history can produce a small number of transitions on a currently healthy link. Use it as supporting context, not as a family switch.

## Distinctive-evidence requirement

The host's evidence must be distinctive — same-subnet peers do not share it. If many hosts share the same anomaly, the cause is upstream (routing / DHCP / ACL / control plane) and this skill does not own it; see Disambiguation.

## Cross-family checks for missing IP

When a host has no IPv4 address and the access interface is UP and stable, more than one upstream cause produces the same symptom. Before submitting a host-side missing-IP fault, rule out: a duplicate MAC against the gateway or another switch, a broken routing / control-plane path to the DHCP server, and an ARP ACL drop or empty (`<incomplete>`) gateway neighbor entry on the host. If any of those fires, the owning family is elsewhere.

## Submit on match

When direct evidence is sufficient (link ruled out, peers don't share the symptom, and the cross-family checks above are clear for missing-IP cases), submit. Do not chain extra probes once the family is confirmed.

## Disambiguation

- **Subnet-wide vs per-host.** If many hosts share the same anomaly, the cause is upstream. Treat this skill as not owning the case and look at routing / DHCP / ACL / control plane.
- **Wrong gateway: host vs DHCP server.** If the DHCP server's config pushes the same wrong gateway value the host has, that's a DHCP fault (`dhcp-fault-skill`), not this one.
- **Missing IP vs link instability.** A transient no-IP reading during link flap is not a host-side missing-IP fault. Require the access interface to be UP and the no-IP state to persist across probes before naming a host-side fault.
- **Missing IP vs ARP drop.** An ARP-filter drop rule or an empty / `<incomplete>` gateway neighbor entry breaks DHCP lease renewal and produces the same symptom as a host-side missing IP. Check the host's neighbor table and ruleset before submitting; if either fires, the owning family is `acl-skill`.
- **ARP poisoning vs ARP ACL.** An empty / `<incomplete>` / zero-MAC gateway entry leans toward `acl-skill` (ARP filtered). A *populated* entry whose MAC does not match the gateway router's real interface MAC, or any entry carrying a static / permanent flag, is ARP cache poisoning. A populated entry matching the gateway router's real MAC is healthy.
- **Host-local DNS misconfig.** A healthy DNS server does not clear a host-side resolver fault; the symptom is the host's resolver differing from same-subnet peers.
