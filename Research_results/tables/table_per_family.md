# Table 3 — Per fault-family overall judge score (test, matched triples)

Mean LLM-judge overall score (1–5) per (fault family, agent). **Bold** = best per row; ✓ = SADE wins (best or tied), ! = SADE loses to a baseline.

| Fault family | n | ReAct (GPT-5) | CC-Baseline | SADE | ✓/! |
|---|---:|---:|---:|---:|:-:|
| `arp_acl_block` | 23 | 2.26 | 3.35 | **4.57** | ✓ |
| `arp_cache_poisoning` | 23 | 3.39 | 3.52 | **3.61** | ✓ |
| `bgp_acl_block` | 7 | 2.29 | 4.00 | **5.00** | ✓ |
| `bgp_asn_misconfig` | 7 | 4.71 | **5.00** | **5.00** | ✓ |
| `bgp_blackhole_route_leak` | 7 | **5.00** | **5.00** | 4.71 | ! |
| `bgp_hijacking` | 3 | **4.33** | 4.00 | **4.33** | ✓ |
| `bgp_missing_route_advertisement` | 7 | 3.57 | **4.29** | 3.14 | ! |
| `bmv2_switch_down` | 4 | 3.50 | **5.00** | 4.75 | ! |
| `dns_lookup_latency` | 3 | **5.00** | **5.00** | 4.33 | ! |
| `dns_port_blocked` | 3 | 2.33 | **4.00** | **4.00** | ✓ |
| `dns_record_error` | 3 | **5.00** | **5.00** | **5.00** | ✓ |
| `dns_service_down` | 3 | **5.00** | 4.33 | **5.00** | ✓ |
| `flow_rule_loop` | 6 | 4.33 | **4.50** | 4.17 | ! |
| `flow_rule_shadowing` | 6 | **4.67** | **4.67** | 4.00 | ! |
| `frr_service_down` | 13 | 4.85 | 4.92 | **5.00** | ✓ |
| `host_crash` | 23 | 4.57 | **4.74** | **4.74** | ✓ |
| `host_incorrect_dns` | 3 | 4.33 | **5.00** | 4.00 | ! |
| `host_incorrect_gateway` | 13 | **5.00** | 4.77 | 4.85 | ! |
| `host_incorrect_ip` | 23 | 4.52 | **4.61** | 4.57 | ! |
| `host_incorrect_netmask` | 13 | **4.31** | 3.92 | 3.62 | ! |
| `host_ip_conflict` | 20 | **4.50** | 3.80 | **4.50** | ✓ |
| `host_missing_ip` | 23 | 4.78 | 4.65 | **4.83** | ✓ |
| `host_static_blackhole` | 7 | **4.71** | 4.57 | **4.71** | ✓ |
| `host_vpn_membership_missing` | 3 | 3.67 | **4.33** | 4.00 | ! |
| `http_acl_block` | 9 | 2.44 | 3.33 | **4.33** | ✓ |
| `icmp_acl_block` | 21 | 2.38 | 4.05 | **4.29** | ✓ |
| `incast_traffic_network_limitation` | 9 | 3.22 | 3.11 | **4.78** | ✓ |
| `link_bandwidth_throttling` | 21 | 2.90 | 4.05 | **4.38** | ✓ |
| `link_detach` | 23 | 4.57 | 3.70 | **4.87** | ✓ |
| `link_down` | 23 | **4.83** | 4.57 | 4.57 | ! |
| `link_flap` | 23 | 3.91 | 3.43 | **4.48** | ✓ |
| `link_fragmentation_disabled` | 23 | 3.00 | 3.00 | **4.17** | ✓ |
| `link_high_packet_corruption` | 23 | **4.78** | 4.48 | 4.48 | ! |
| `mac_address_conflict` | 23 | 2.43 | 2.09 | **4.35** | ✓ |
| `mpls_label_limit_exceeded` | 1 | **3.00** | **3.00** | **3.00** | ✓ |
| `ospf_acl_block` | 3 | 2.33 | 4.00 | **5.00** | ✓ |
| `ospf_area_misconfiguration` | 3 | **5.00** | **5.00** | **5.00** | ✓ |
| `ospf_neighbor_missing` | 3 | **5.00** | 4.00 | **5.00** | ✓ |
| `p4_compilation_error_parser_state` | 4 | 2.50 | **3.50** | 2.75 | ! |
| `p4_header_definition_error` | 4 | 3.00 | **3.50** | 3.25 | ! |
| `p4_table_entry_misconfig` | 4 | 3.25 | **4.25** | 3.00 | ! |
| `p4_table_entry_missing` | 4 | 3.00 | **3.75** | 3.00 | ! |
| `receiver_resource_contention` | 8 | **2.75** | 2.62 | 2.38 | ! |
| `sdn_controller_crash` | 6 | 4.67 | **5.00** | 4.50 | ! |
| `sender_application_delay` | 9 | 2.44 | **2.56** | **2.56** | ✓ |
| `sender_resource_contention` | 9 | **3.67** | 2.78 | 2.67 | ! |
| `southbound_port_block` | 6 | 2.83 | 3.00 | **4.67** | ✓ |
| `southbound_port_mismatch` | 6 | **4.83** | **4.83** | **4.83** | ✓ |
| `web_dos_attack` | 9 | 2.89 | 3.11 | **4.00** | ✓ |