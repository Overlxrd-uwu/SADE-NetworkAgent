# Failed Case Summary

Source:
- [results/0_summary/evaluation_summary.csv](../results/0_summary/evaluation_summary.csv)
- [benchmark/benchmark_failed.csv](../benchmark/benchmark_failed.csv)

Filter rule used:
- fail if `detection_score != 1`
- also fail if `detection_score == 1` but `llm_judge_final_outcome_score < 3`

## Overview

- Total evaluated rows: `108`
- Total failed rows selected for rerun: `40`
- Scenario scope in this run: `ospf_enterprise_dhcp` only

## What Went Wrong

- `35/40` failures are hard benchmark failures where `detection_score != 1`
  This usually means no submission, invalid submission, or a wrong final structured answer even if the trace looked reasonable.
- `5/40` failures still detected an anomaly (`detection_score == 1`) but had weak final outcome quality (`llm_judge_final_outcome_score < 3`)
  These are low-confidence or poor-quality end results rather than total misses.

## By Topology Size

- `l`: `17`
- `m`: `11`
- `s`: `12`

Large topologies are still the biggest source of failures, but the corrected rule also pulled in a few smaller-topology weak-final-outcome cases.

## Repeated Problem Families

- `host_incorrect_dns`: `3`
- `host_incorrect_ip`: `3`
- `arp_cache_poisoning`: `3`
- `link_bandwidth_throttling`: `3`
- `receiver_resource_contention`: `3`
- `host_incorrect_netmask`: `2`
- `host_missing_ip`: `2`
- `link_down`: `2`
- `ospf_acl_block`: `2`
- `web_dos_attack`: `2`
- `load_balancer_overload`: `2`

These are the main clusters dragging the run down.

## Notable Takeaways

- Most damage is still from `detection_score = -1`, which points more to no-submit / malformed-submit / final-answer-path issues than to pure reasoning quality.
- The corrected rule adds several rows where detection succeeded but the final outcome score was very weak, so the rerun set is now slightly larger and more faithful to the end-task behavior.
- The failures are spread across host config, ACL, L2/L3 security, OSPF/FRR, DoS/resource contention, and performance faults, so the pain is not isolated to one single family.

## Failed Cases

| Problem | Scenario | Topo | Session | Detection | Final Outcome | Why included |
|---|---|---:|---|---:|---:|---|
| `host_ip_conflict` | `ospf_enterprise_dhcp` | `l` | `0418015102` | `0.0` | `1` | detection failed |
| `host_incorrect_dns` | `ospf_enterprise_dhcp` | `s` | `0418020125` | `-1.0` | `1` | detection failed |
| `host_incorrect_dns` | `ospf_enterprise_dhcp` | `m` | `0418020913` | `-1.0` | `1` | detection failed |
| `host_incorrect_dns` | `ospf_enterprise_dhcp` | `l` | `0418021716` | `-1.0` | `1` | detection failed |
| `host_incorrect_gateway` | `ospf_enterprise_dhcp` | `l` | `0418023712` | `-1.0` | `1` | detection failed |
| `host_incorrect_ip` | `ospf_enterprise_dhcp` | `s` | `0418024927` | `-1.0` | `1` | detection failed |
| `host_incorrect_ip` | `ospf_enterprise_dhcp` | `m` | `0418025643` | `-1.0` | `3` | detection failed |
| `host_incorrect_ip` | `ospf_enterprise_dhcp` | `l` | `0418031004` | `-1.0` | `1` | detection failed |
| `host_incorrect_netmask` | `ospf_enterprise_dhcp` | `s` | `0418032308` | `1.0` | `1` | final outcome < 3 |
| `host_incorrect_netmask` | `ospf_enterprise_dhcp` | `m` | `0418032834` | `-1.0` | `1` | detection failed |
| `host_missing_ip` | `ospf_enterprise_dhcp` | `s` | `0418034512` | `-1.0` | `4` | detection failed |
| `host_missing_ip` | `ospf_enterprise_dhcp` | `l` | `0418040137` | `-1.0` | `1` | detection failed |
| `link_down` | `ospf_enterprise_dhcp` | `s` | `0418050130` | `1.0` | `2` | final outcome < 3 |
| `link_down` | `ospf_enterprise_dhcp` | `l` | `0418051104` | `-1.0` | `1` | detection failed |
| `link_fragmentation_disabled` | `ospf_enterprise_dhcp` | `l` | `0418055638` | `-1.0` | `1` | detection failed |
| `arp_acl_block` | `ospf_enterprise_dhcp` | `l` | `0418062245` | `-1.0` | `1` | detection failed |
| `dns_port_blocked` | `ospf_enterprise_dhcp` | `m` | `0418063853` | `1.0` | `1` | final outcome < 3 |
| `http_acl_block` | `ospf_enterprise_dhcp` | `s` | `0418065431` | `-1.0` | `5` | detection failed |
| `icmp_acl_block` | `ospf_enterprise_dhcp` | `m` | `0418072615` | `-1.0` | `1` | detection failed |
| `ospf_acl_block` | `ospf_enterprise_dhcp` | `s` | `0418074740` | `-1.0` | `2` | detection failed |
| `ospf_acl_block` | `ospf_enterprise_dhcp` | `m` | `0418075422` | `-1.0` | `1` | detection failed |
| `mac_address_conflict` | `ospf_enterprise_dhcp` | `l` | `0418083836` | `-1.0` | `1` | detection failed |
| `ospf_area_misconfiguration` | `ospf_enterprise_dhcp` | `l` | `0418090152` | `-1.0` | `1` | detection failed |
| `ospf_neighbor_missing` | `ospf_enterprise_dhcp` | `m` | `0418091837` | `-1.0` | `1` | detection failed |
| `frr_service_down` | `ospf_enterprise_dhcp` | `l` | `0418095224` | `0.0` | `1` | detection failed |
| `arp_cache_poisoning` | `ospf_enterprise_dhcp` | `s` | `0418100234` | `-1.0` | `1` | detection failed |
| `arp_cache_poisoning` | `ospf_enterprise_dhcp` | `m` | `0418101019` | `-1.0` | `1` | detection failed |
| `arp_cache_poisoning` | `ospf_enterprise_dhcp` | `l` | `0418101950` | `0.0` | `1` | detection failed |
| `dhcp_spoofed_dns` | `ospf_enterprise_dhcp` | `s` | `0418103211` | `1.0` | `1` | final outcome < 3 |
| `web_dos_attack` | `ospf_enterprise_dhcp` | `s` | `0418111101` | `-1.0` | `5` | detection failed |
| `web_dos_attack` | `ospf_enterprise_dhcp` | `l` | `0418112914` | `-1.0` | `5` | detection failed |
| `link_bandwidth_throttling` | `ospf_enterprise_dhcp` | `s` | `0418115543` | `-1.0` | `4` | detection failed |
| `link_bandwidth_throttling` | `ospf_enterprise_dhcp` | `m` | `0418120409` | `-1.0` | `1` | detection failed |
| `link_bandwidth_throttling` | `ospf_enterprise_dhcp` | `l` | `0418121631` | `-1.0` | `2` | detection failed |
| `load_balancer_overload` | `ospf_enterprise_dhcp` | `m` | `0418131015` | `0.0` | `1` | detection failed |
| `load_balancer_overload` | `ospf_enterprise_dhcp` | `l` | `0418131846` | `0.0` | `1` | detection failed |
| `receiver_resource_contention` | `ospf_enterprise_dhcp` | `s` | `0418132954` | `-1.0` | `1` | detection failed |
| `receiver_resource_contention` | `ospf_enterprise_dhcp` | `m` | `0418133758` | `-1.0` | `1` | detection failed |
| `receiver_resource_contention` | `ospf_enterprise_dhcp` | `l` | `0418134618` | `1.0` | `1` | final outcome < 3 |
| `sender_application_delay` | `ospf_enterprise_dhcp` | `l` | `0418140709` | `-1.0` | `1` | detection failed |
