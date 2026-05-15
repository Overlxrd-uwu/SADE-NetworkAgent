# Cases where every baseline fails and SADE succeeds

Strict filter applied: SADE's `llm_judge_final_outcome_score >= 4` AND both ReAct (GPT-5) and CC-Baseline (Claude Code, no SADE) scored `<= 2`. These are the cleanest demonstrations of SADE's diagnostic-workflow advantage — the same model class (Sonnet) fails without scaffolding (CC-Baseline), and a different framework with a stronger model (GPT-5) also fails. The only thing differentiating SADE on these cases is the SADE workflow itself.

Total matching cases: **79**.

---

## Cross-cutting failure-mode summary

How each baseline fails on these cases (categorised by submission shape vs ground truth):

| Failure mode | ReAct (GPT-5) | CC-Baseline |
|---|---:|---:|
| empty submission | 22 | 5 |
| no submission | 13 | 35 |
| wrong device | 0 | 1 |
| wrong family + wrong device | 34 | 30 |
| wrong fault family | 10 | 8 |

Tool-call medians on these cases:

| Agent | median tool_calls |
|---|---:|
| ReAct (GPT-5) | 28 |
| CC-Baseline | 37 |
| **SADE** | **19** |

Most common patterns: **CC-Baseline runs out of turns without finalising** (no submit), and **ReAct converges on a neighbouring fault family** (right symptom, wrong label). SADE's phase gates force an early commitment to a fault family and the skill scaffolding tells the agent which decisive probe to run, so it submits faster and lands on the right label.

---

## Case 1: `arp_acl_block` on `dc_clos_bgp` (l)

**Ground truth.** root_cause_name = `['arp_acl_block']`, faulty_devices = `['pc_3_3']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0425045438` | 1 | `is_anomaly=False`, `root_cause_name=['sender_resource_contention']`, `faulty_devices=[]` | wrong family + wrong device |
| **CC-Baseline** | `0426045402` | 1 | _no submit() call — agent never finalised a diagnosis_ | no submission |
| **SADE** | `0429025855` | 5 | `is_anomaly=True`, `root_cause_name=['arp_acl_block']`, `faulty_devices=['pc_3_3']` | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (21 tool calls). Submitted root_cause_name=['sender_resource_contention'], faulty_devices=[]; ground truth root_cause_name=['arp_acl_block'], faulty_devices=['pc_3_3'].
- **CC-Baseline** (33 tool calls). Agent never called `submit()` — exhausted its turn budget without finalising.

**What SADE did differently**

- 26 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → ToolSearch → exec_shell → exec_shell → Skill → … (12 more) … → exec_shell → Skill → exec_shell → exec_shell → Skill → ToolSearch → submit).
- Decisive reasoning (last thinking before `submit`):  
  > The acl-skill confirms the decision table: `table arp filter` with `drop` rules ? `arp_acl_block`. The faulty device is `pc_3_3` since it owns the matching drop rule.  Now let me submit.

---

## Case 2: `arp_acl_block` on `dc_clos_bgp` (m)

**Ground truth.** root_cause_name = `['arp_acl_block']`, faulty_devices = `['pc_0_1']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0425045141` | 1 | _submitted empty diagnosis_ | empty submission |
| **CC-Baseline** | `0426044337` | 1 | `is_anomaly=True`, `root_cause_name=['link_detach']`, `faulty_devices=['pc_0_2', 'leaf_router_0_2']` | wrong family + wrong device |
| **SADE** | `0429025420` | 5 | `is_anomaly=True`, `root_cause_name=['arp_acl_block']`, `faulty_devices=['pc_0_1']` | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (13 tool calls). Submitted with empty root_cause_name / faulty_devices.
- **CC-Baseline** (20 tool calls). Submitted root_cause_name=['link_detach'], faulty_devices=['pc_0_2', 'leaf_router_0_2']; ground truth root_cause_name=['arp_acl_block'], faulty_devices=['pc_0_1'].

**What SADE did differently**

- 17 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → ToolSearch → exec_shell → exec_shell → exec_shell → … (3 more) … → ToolSearch → Skill → exec_shell → exec_shell → Skill → ToolSearch → submit).
- Decisive reasoning (last thinking before `submit`):  
  > The skill confirms: - `table arp filter` with `drop` rules ? `arp_acl_block` - Faulty device: `pc_0_1` (owns the drop rule)  Now let me submit.

---

## Case 3: `arp_acl_block` on `dc_clos_bgp` (s)

**Ground truth.** root_cause_name = `['arp_acl_block']`, faulty_devices = `['pc_0_1']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0425044754` | 1 | _submitted empty diagnosis_ | empty submission |
| **CC-Baseline** | `0426043452` | 2 | `is_anomaly=True`, `root_cause_name=['host_crash']`, `faulty_devices=['pc_0_1']` | wrong fault family |
| **SADE** | `0429025014` | 5 | `is_anomaly=True`, `root_cause_name=['arp_acl_block']`, `faulty_devices=['pc_0_1']` | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (16 tool calls). Submitted with empty root_cause_name / faulty_devices.
- **CC-Baseline** (31 tool calls). Got the device right but submitted root_cause_name=['host_crash'] (ground truth ['arp_acl_block']).

**What SADE did differently**

- 23 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → ToolSearch → exec_shell → exec_shell → Skill → … (9 more) … → get_host_net_config → exec_shell → exec_shell → exec_shell → Skill → ToolSearch → submit).
- Decisive reasoning (last thinking before `submit`):  
  > The acl-skill confirms: `table arp filter` with `drop` rules ? `arp_acl_block`. The faulty device is `pc_0_1` (the device that owns the matching drop rule).  Let me now submit.

---

## Case 4: `arp_acl_block` on `ospf_enterprise_static` (l)

**Ground truth.** root_cause_name = `['arp_acl_block']`, faulty_devices = `['host_2_2_2_4']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0425051958` | 1 | _submitted empty diagnosis_ | empty submission |
| **CC-Baseline** | `0426055046` | 1 | _no submit() call — agent never finalised a diagnosis_ | no submission |
| **SADE** | `0429033333` | 5 | `is_anomaly=True`, `root_cause_name=['arp_acl_block']`, `faulty_devices=['host_2_2_2_4']` | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (33 tool calls). Submitted with empty root_cause_name / faulty_devices.
- **CC-Baseline** (47 tool calls). Agent never called `submit()` — exhausted its turn budget without finalising.

**What SADE did differently**

- 18 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → ToolSearch → Skill → Bash → ToolSearch → … (4 more) … → Skill → exec_shell → exec_shell → exec_shell → Skill → ToolSearch → submit).
- Decisive reasoning (last thinking before `submit`):  
  > The ACL skill confirms: `table arp filter` with `drop` rules ? `arp_acl_block`. The faulty device is `host_2_2_2_4`.  Now I can submit.

---

## Case 5: `arp_acl_block` on `ospf_enterprise_static` (m)

**Ground truth.** root_cause_name = `['arp_acl_block']`, faulty_devices = `['host_1_1_2_2']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0425051459` | 1 | `is_anomaly=True`, `root_cause_name=['ospf_neighbor_missing']`, `faulty_devices=['switch_dist_1_1', 'switch_dist_2_1']` | wrong family + wrong device |
| **CC-Baseline** | `0426053552` | 2 | _no submit() call — agent never finalised a diagnosis_ | no submission |
| **SADE** | `0429032450` | 5 | `is_anomaly=True`, `root_cause_name=['arp_acl_block']`, `faulty_devices=['host_1_1_2_2']` | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (39 tool calls). Submitted root_cause_name=['ospf_neighbor_missing'], faulty_devices=['switch_dist_1_1', 'switch_dist_2_1']; ground truth root_cause_name=['arp_acl_block'], faulty_devices=['host_1_1_2_2'].
- **CC-Baseline** (54 tool calls). Agent never called `submit()` — exhausted its turn budget without finalising.

**What SADE did differently**

- 30 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → ToolSearch → exec_shell → exec_shell → exec_shell → … (16 more) … → ToolSearch → Bash → Bash → Skill → exec_shell → ToolSearch → submit).
- Decisive reasoning (last thinking before `submit`):  
  > Clear fingerprint found:  ``` table arp filter {     chain input {         type filter hook input priority filter; policy accept;         drop     }      chain output {         type filter hook output priority filter; policy accept;         drop     } } ```  This is `table arp filter` with `drop` rules in BOTH input and output chains. Per the decision table:  | `table arp filter` with `drop` rules | `arp_acl_block` |  The faulty device is `host_1_1_2_2`.   The ARP filter on `host_1_1_2_2` blocks all ARP traffic in both directions, preventing it from sending ARP requests to resolve gateway MACs or receiving replies, which isolates it from any communication beyond cached entries. This is the r…

---

## Case 6: `arp_acl_block` on `ospf_enterprise_static` (s)

**Ground truth.** root_cause_name = `['arp_acl_block']`, faulty_devices = `['host_1_1_1_1']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0425051026` | 1 | `is_anomaly=True`, `root_cause_name=['ospf_neighbor_missing']`, `faulty_devices=['switch_dist_1_1', 'switch_dist_2_1']` | wrong family + wrong device |
| **CC-Baseline** | `0426052624` | 1 | _no submit() call — agent never finalised a diagnosis_ | no submission |
| **SADE** | `0429031836` | 5 | `is_anomaly=True`, `root_cause_name=['arp_acl_block']`, `faulty_devices=['host_1_1_1_1']` | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (38 tool calls). Submitted root_cause_name=['ospf_neighbor_missing'], faulty_devices=['switch_dist_1_1', 'switch_dist_2_1']; ground truth root_cause_name=['arp_acl_block'], faulty_devices=['host_1_1_1_1'].
- **CC-Baseline** (41 tool calls). Agent never called `submit()` — exhausted its turn budget without finalising.

**What SADE did differently**

- 24 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → ToolSearch → exec_shell → exec_shell → exec_shell → … (10 more) … → Skill → exec_shell → exec_shell → exec_shell → exec_shell → ToolSearch → submit).
- Decisive reasoning (last thinking before `submit`):  
  > …_2_1_1_1 ? web_server_2 case, the direct IP ping to 10.200.0.5 succeeded, which suggests the connectivity is fine but the hostname resolution is what's failing. The DNS server is returning NXDOMAIN and REFUSED responses for "web_server_2" because that container name isn't registered in the lab's DNS zone?the actual records are probably "web2.local" or similar. So the "unknown" ping results aren't failures, just the test framework trying to resolve container names that don't exist in DNS, while direct IP pings work fine. But it's odd that host_1_1_1_1 also shows unknown for web_server_2, which suggests something else might be going on. The DNS zone only has records for web0.local through web…

---

## Case 7: `arp_acl_block` on `p4_bloom_filter` (-)

**Ground truth.** root_cause_name = `['arp_acl_block']`, faulty_devices = `['host_2']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0425060822` | 1 | _submitted empty diagnosis_ | empty submission |
| **CC-Baseline** | `0426070735` | 1 | `is_anomaly=True`, `root_cause_name=['p4_aggressive_detection_thresholds']`, `faulty_devices=['switch_1', 'switch_2']` | wrong family + wrong device |
| **SADE** | `0429044057` | 5 | `is_anomaly=True`, `root_cause_name=['arp_acl_block']`, `faulty_devices=['host_2']` | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (15 tool calls). Submitted with empty root_cause_name / faulty_devices.
- **CC-Baseline** (29 tool calls). Submitted root_cause_name=['p4_aggressive_detection_thresholds'], faulty_devices=['switch_1', 'switch_2']; ground truth root_cause_name=['arp_acl_block'], faulty_devices=['host_2'].

**What SADE did differently**

- 22 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → ToolSearch → Skill → Bash → Bash → … (8 more) … → exec_shell → bmv2_get_log → bmv2_get_log → ToolSearch → Skill → ToolSearch → submit).
- Decisive reasoning (last thinking before `submit`):  
  > The acl-skill decision table confirms: `table arp filter` with `drop` rules ? `arp_acl_block`.  Faulty device: `host_2` (that's where the nft ruleset shows `table arp filter` with `drop` on both input and output).  Let me now submit.

---

## Case 8: `arp_acl_block` on `p4_counter` (-)

**Ground truth.** root_cause_name = `['arp_acl_block']`, faulty_devices = `['pc3']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0425061041` | 1 | _no submit() call — agent never finalised a diagnosis_ | no submission |
| **CC-Baseline** | `0426070956` | 1 | _submitted empty diagnosis_ | empty submission |
| **SADE** | `0429044400` | 5 | `is_anomaly=True`, `root_cause_name=['arp_acl_block']`, `faulty_devices=['pc3']` | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (36 tool calls). Agent never called `submit()` — exhausted its turn budget without finalising.
- **CC-Baseline** (43 tool calls). Submitted with empty root_cause_name / faulty_devices.

**What SADE did differently**

- 12 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → ToolSearch → Skill → Bash → Bash → Skill → exec_shell → Skill → ToolSearch → submit).
- Decisive reasoning (last thinking before `submit`):  
  > The ACL skill confirms the fingerprint. The `nft list ruleset` on pc3 shows:  ``` table arp filter {     chain input {         type filter hook input priority filter; policy accept;         drop     }     chain output {         type filter hook output priority filter; policy accept;         drop     } } ```  This matches the decision table row: `table arp filter` with `drop` rules ? `arp_acl_block`  The faulty device is **pc3** (the device owning the matching drop rule).  Now I need to submit. Let me re-enter the acl-skill to confirm the canonical root_cause_name, then submit.   I've confirmed the root cause is `arp_acl_block` on pc3 with high confidence based on the direct fingerprint match…

---

## Case 9: `arp_acl_block` on `p4_int` (-)

**Ground truth.** root_cause_name = `['arp_acl_block']`, faulty_devices = `['pc1']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0425061334` | 1 | `is_anomaly=True`, `root_cause_name=['p4_table_entry_missing']`, `faulty_devices=['leaf1']` | wrong family + wrong device |
| **CC-Baseline** | `0501094740` | 1 | _no submit() call — agent never finalised a diagnosis_ | no submission |
| **SADE** | `0501140414` | 5 | `is_anomaly=True`, `root_cause_name=['arp_acl_block']`, `faulty_devices=['pc1']` | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (27 tool calls). Submitted root_cause_name=['p4_table_entry_missing'], faulty_devices=['leaf1']; ground truth root_cause_name=['arp_acl_block'], faulty_devices=['pc1'].
- **CC-Baseline** (49 tool calls). Agent never called `submit()` — exhausted its turn budget without finalising.

**What SADE did differently**

- 14 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → Skill → Bash → Bash → Skill → Bash → ToolSearch → exec_shell → Bash → Skill → ToolSearch → submit).
- Decisive reasoning (last thinking before `submit`):  
  > Now let me submit the result with the confirmed findings: - is_anomaly: true - root_cause_name: ["arp_acl_block"] - faulty_devices: ["pc1"]

---

## Case 10: `arp_acl_block` on `p4_mpls` (-)

**Ground truth.** root_cause_name = `['arp_acl_block']`, faulty_devices = `['host_1']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0425061809` | 1 | `is_anomaly=True`, `root_cause_name=['link_bandwidth_throttling']`, `faulty_devices=[]` | wrong family + wrong device |
| **CC-Baseline** | `0426071749` | 1 | _no submit() call — agent never finalised a diagnosis_ | no submission |
| **SADE** | `0429044654` | 5 | `is_anomaly=True`, `root_cause_name=['arp_acl_block']`, `faulty_devices=['host_1']` | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (24 tool calls). Submitted root_cause_name=['link_bandwidth_throttling'], faulty_devices=[]; ground truth root_cause_name=['arp_acl_block'], faulty_devices=['host_1'].
- **CC-Baseline** (46 tool calls). Agent never called `submit()` — exhausted its turn budget without finalising.

**What SADE did differently**

- 21 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → Skill → ToolSearch → Bash → Bash → … (7 more) … → ToolSearch → exec_shell → exec_shell → bmv2_show_tables → Skill → ToolSearch → submit).
- Decisive reasoning (last thinking before `submit`):  
  > The acl-skill confirms the exact fingerprint:  | Fingerprint | Submit | |---|---| | `table arp filter` with `drop` rules | `arp_acl_block` |  host_1 has exactly this: ``` table arp filter {     chain input {         type filter hook input priority filter; policy accept;         drop     }     chain output {         type filter hook output priority filter; policy accept;         drop     } } ```  This is a direct match. The faulty device is host_1 (it owns the matching drop rule).   I've got a complete match with the decision table, so I'm submitting the result now without running any additional probes.

---

## Case 11: `arp_acl_block` on `rip_small_internet_vpn` (s)

**Ground truth.** root_cause_name = `['arp_acl_block']`, faulty_devices = `['host_2']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0425052458` | 1 | _submitted empty diagnosis_ | empty submission |
| **CC-Baseline** | `0426055938` | 1 | _no submit() call — agent never finalised a diagnosis_ | no submission |
| **SADE** | `0429033839` | 5 | `is_anomaly=True`, `root_cause_name=['arp_acl_block']`, `faulty_devices=['host_2']` | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (44 tool calls). Submitted with empty root_cause_name / faulty_devices.
- **CC-Baseline** (46 tool calls). Agent never called `submit()` — exhausted its turn budget without finalising.

**What SADE did differently**

- 15 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → ToolSearch → exec_shell → exec_shell → exec_shell → … (1 more) … → exec_shell → exec_shell → exec_shell → exec_shell → Skill → ToolSearch → submit).
- Decisive reasoning (last thinking before `submit`):  
  > The acl-skill confirms my finding. The decision table clearly shows:  | `table arp filter` with `drop` rules | `arp_acl_block` |  And the faulty device is `host_2` (the device that owns the matching drop rule).  Let me now submit.

---

## Case 12: `arp_acl_block` on `sdn_clos` (s)

**Ground truth.** root_cause_name = `['arp_acl_block']`, faulty_devices = `['host_2_1']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0425055128` | 1 | `is_anomaly=True`, `root_cause_name=['link_bandwidth_throttling']`, `faulty_devices=['leaf_1']` | wrong family + wrong device |
| **CC-Baseline** | `0426064924` | 1 | `is_anomaly=True`, `root_cause_name=['southbound_port_mismatch']`, `faulty_devices=['leaf_1']` | wrong family + wrong device |
| **SADE** | `0429041708` | 5 | `is_anomaly=True`, `root_cause_name=['arp_acl_block']`, `faulty_devices=['host_2_1']` | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (43 tool calls). Submitted root_cause_name=['link_bandwidth_throttling'], faulty_devices=['leaf_1']; ground truth root_cause_name=['arp_acl_block'], faulty_devices=['host_2_1'].
- **CC-Baseline** (25 tool calls). Submitted root_cause_name=['southbound_port_mismatch'], faulty_devices=['leaf_1']; ground truth root_cause_name=['arp_acl_block'], faulty_devices=['host_2_1'].

**What SADE did differently**

- 25 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → ToolSearch → exec_shell → exec_shell → exec_shell → … (11 more) … → exec_shell → exec_shell → exec_shell → exec_shell → Skill → ToolSearch → submit).
- Decisive reasoning (last thinking before `submit`):  
  > The skill confirms the fingerprint:  | Fingerprint in ruleset | Submit | |---|---| | `table arp filter` with `drop` rules | `arp_acl_block` |  We found exactly this on `host_2_1`: ``` table arp filter {     chain input { drop }     chain output { drop } } ```  The faulty device is `host_2_1` (the device that owns the matching drop rule).  Now let me submit.

---

## Case 13: `arp_cache_poisoning` on `ospf_enterprise_static` (l)

**Ground truth.** root_cause_name = `['arp_cache_poisoning']`, faulty_devices = `['host_2_3_1_2']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0425200736` | 1 | _no submit() call — agent never finalised a diagnosis_ | no submission |
| **CC-Baseline** | `0427040250` | 1 | _no submit() call — agent never finalised a diagnosis_ | no submission |
| **SADE** | `0429163000` | 5 | `is_anomaly=True`, `root_cause_name=['arp_cache_poisoning']`, `faulty_devices=['host_2_3_1_2']` | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (31 tool calls). Agent never called `submit()` — exhausted its turn budget without finalising.
- **CC-Baseline** (26 tool calls). Agent never called `submit()` — exhausted its turn budget without finalising.

**What SADE did differently**

- 14 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → Skill → Bash → ToolSearch → exec_shell → exec_shell → Skill → exec_shell → exec_shell → exec_shell → exec_shell → submit).
- Decisive reasoning (last thinking before `submit`):  
  > The real gateway `10.2.3.1` is hosted on `br0` of `switch_dist_2_3`, with MAC address `0e:74:fd:44:ce:12`.  But `host_2_3_1_2` has a PERMANENT ARP entry mapping `10.2.3.1` ? `00:11:22:33:44:55`.  `00:11:22:33:44:55` ? `0e:74:fd:44:ce:12`   This confirms the ARP cache poisoning ? the static entry points to a fake MAC address, so all cross-subnet traffic gets misdirected and fails. Now I'm moving to Phase 5 to verify the root cause name and identify the faulty devices against the fault table.  The root cause is `arp_cache_poisoning` and the faulty device is `host_2_3_1_2`. I need to confirm that `arp_cache_poisoning` exists in the available problems list before submitting.

---

## Case 14: `arp_cache_poisoning` on `ospf_enterprise_static` (m)

**Ground truth.** root_cause_name = `['arp_cache_poisoning']`, faulty_devices = `['host_2_1_1_2']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0425200128` | 1 | _no submit() call — agent never finalised a diagnosis_ | no submission |
| **CC-Baseline** | `0427035101` | 1 | _no submit() call — agent never finalised a diagnosis_ | no submission |
| **SADE** | `0429162153` | 5 | `is_anomaly=True`, `root_cause_name=['arp_cache_poisoning']`, `faulty_devices=['host_2_1_1_2']` | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (23 tool calls). Agent never called `submit()` — exhausted its turn budget without finalising.
- **CC-Baseline** (67 tool calls). Agent never called `submit()` — exhausted its turn budget without finalising.

**What SADE did differently**

- 29 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → ToolSearch → exec_shell → exec_shell → exec_shell → … (15 more) … → Bash → Bash → exec_shell → exec_shell → Skill → ToolSearch → submit).
- Decisive reasoning (last thinking before `submit`):  
  > The host-ip-skill decision table confirms exactly what I observed:  | Signal on the host | Submit | Faulty devices | |---|---|---| | Static / `PERMANENT` ARP entry on the host, OR host's gateway MAC differs from the gateway router's real interface MAC | `arp_cache_poisoning` | the host |  The evidence is clear: - `host_2_1_1_2` has `10.2.1.1 dev eth0 lladdr 00:11:22:33:44:55 PERMANENT` ? a static/PERMANENT ARP entry for the gateway   - The fabricated MAC `00:11:22:33:44:55` doesn't match the real router MAC `3e:54:b2:26:15:63` that all peers agree on  This is a perfect match for the decision table rule, so I'm ready to submit the `arp_cache_poisoning` diagnosis with `host_2_1_1_2` as the fau…

---

## Case 15: `bgp_acl_block` on `dc_clos_service` (l)

**Ground truth.** root_cause_name = `['bgp_acl_block']`, faulty_devices = `['spine_router_2_3']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0425064007` | 1 | `is_anomaly=True`, `root_cause_name=['host_incorrect_dns']`, `faulty_devices=['client_0']` | wrong family + wrong device |
| **CC-Baseline** | `0426083421` | 1 | _no submit() call — agent never finalised a diagnosis_ | no submission |
| **SADE** | `0429051844` | 5 | `is_anomaly=True`, `root_cause_name=['bgp_acl_block']`, `faulty_devices=['spine_router_2_3']` | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (12 tool calls). Submitted root_cause_name=['host_incorrect_dns'], faulty_devices=['client_0']; ground truth root_cause_name=['bgp_acl_block'], faulty_devices=['spine_router_2_3'].
- **CC-Baseline** (53 tool calls). Agent never called `submit()` — exhausted its turn budget without finalising.

**What SADE did differently**

- 13 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → ToolSearch → Skill → ToolSearch → Bash → Bash → Skill → ToolSearch → exec_shell → ToolSearch → submit).
- Decisive reasoning (last thinking before `submit`):  
  > The confirmation is clear. `spine_router_2_3` has nftables rules that drop TCP port 179 (BGP) in ALL chains: input, forward, and output. This means: 1. No BGP sessions can be established TO this router (input chain drops dport 179) 2. No BGP sessions can be forwarded THROUGH this router (forward chain drops dport/sport 179)   3. No BGP sessions can be established FROM this router (output chain drops dport 179)  This is a textbook `bgp_acl_block`. The faulty device is `spine_router_2_3`.   I have a complete match against the decision table, so I'm ready to submit the root cause: `bgp_acl_block` on `spine_router_2_3`.  The impact makes sense too?with BGP blocked on all three chains, the spine …

---

## Case 16: `bgp_acl_block` on `dc_clos_service` (s)

**Ground truth.** root_cause_name = `['bgp_acl_block']`, faulty_devices = `['spine_router_0_1']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0425063359` | 1 | `is_anomaly=True`, `root_cause_name=['bgp_blackhole_route_leak']`, `faulty_devices=['leaf_router_0_0', 'leaf_router_0_1']` | wrong family + wrong device |
| **CC-Baseline** | `0426081328` | 2 | _no submit() call — agent never finalised a diagnosis_ | no submission |
| **SADE** | `0429050856` | 5 | `is_anomaly=True`, `root_cause_name=['bgp_acl_block']`, `faulty_devices=['spine_router_0_1']` | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (19 tool calls). Submitted root_cause_name=['bgp_blackhole_route_leak'], faulty_devices=['leaf_router_0_0', 'leaf_router_0_1']; ground truth root_cause_name=['bgp_acl_block'], faulty_devices=['spine_router_0_1'].
- **CC-Baseline** (66 tool calls). Agent never called `submit()` — exhausted its turn budget without finalising.

**What SADE did differently**

- 14 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → ToolSearch → Skill → Bash → Bash → Bash → Skill → ToolSearch → exec_shell → frr_exec → ToolSearch → submit).
- Decisive reasoning (last thinking before `submit`):  
  > …BGP connections will be able to form through this router. flowing and the hold timer expires (180s).  The sessions show "up for 00:01:56" which is very short - the lab was recently started. The ACL was likely injected at startup or shortly after, and the sessions are currently established but will eventually be disrupted.  Actually wait - the keepalives sent: 2, received: 1. With a 60s keepalive interval and 1:56 uptime, that means roughly 2 keepalives should have been sent. But the ACL is in the OUTPUT chain too, so outgoing keepalives from spine_router_0_1 are being dropped. And the ACL in INPUT drops incoming keepalives. So existing TCP sessions may still be "established" at the kernel l…

---

## Case 17: `bgp_acl_block` on `simple_bgp` (-)

**Ground truth.** root_cause_name = `['bgp_acl_block']`, faulty_devices = `['router2']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0425064350` | 1 | _submitted empty diagnosis_ | empty submission |
| **CC-Baseline** | `0426084413` | 1 | _submitted empty diagnosis_ | empty submission |
| **SADE** | `0429052315` | 5 | `is_anomaly=True`, `root_cause_name=['bgp_acl_block']`, `faulty_devices=['router2']` | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (11 tool calls). Submitted with empty root_cause_name / faulty_devices.
- **CC-Baseline** (21 tool calls). Submitted with empty root_cause_name / faulty_devices.

**What SADE did differently**

- 10 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → Skill → Bash → Bash → Bash → Skill → ToolSearch → submit).
- Decisive reasoning (last thinking before `submit`):  
  > The ACL skill confirms the fingerprint. The `infra_sweep` already showed the exact drop rules on `router2`: - `tcp dport 179 drop` - `tcp sport 179 drop`  This matches the decision table row: **TCP port 179 drop rule ? `bgp_acl_block`**  The faulty device is `router2`.  I have direct evidence. Let me confirm with a quick `nft list ruleset` on `router2` to get the exact ruleset, then submit.  Actually, the infra_sweep already showed the exact rules repeated 3 times (probably 3 tables/chains). The evidence is already conclusive.   The decision table is clear?when direct evidence fully matches a row, I should submit. The infra_sweep provides exactly what I need: `router2` has the BGP port 179 d…

---

## Case 18: `bgp_missing_route_advertisement` on `dc_clos_bgp` (l)

**Ground truth.** root_cause_name = `['bgp_missing_route_advertisement']`, faulty_devices = `['leaf_router_0_1']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0425104040` | 1 | `is_anomaly=True`, `root_cause_name=['bgp_acl_block', 'bgp_blackhole_route_leak']`, `faulty_devices=['spine_router_0_0', 'leaf at 172.16.1.15 (AS 65207)']` | wrong family + wrong device |
| **CC-Baseline** | `0426145843` | 2 | `is_anomaly=True`, `root_cause_name=['frr_service_down']`, `faulty_devices=['spine_router_0_1']` | wrong family + wrong device |
| **SADE** | `0429041439` | 5 | `is_anomaly=True`, `root_cause_name=['bgp_missing_route_advertisement']`, `faulty_devices=['leaf_router_0_1']` | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (20 tool calls). Submitted root_cause_name=['bgp_acl_block', 'bgp_blackhole_route_leak'], faulty_devices=['spine_router_0_0', 'leaf at 172.16.1.15 (AS 65207)']; ground truth root_cause_name=['bgp_missing_route_advertisement'], faulty_devices=['leaf_router_0_1'].
- **CC-Baseline** (37 tool calls). Submitted root_cause_name=['frr_service_down'], faulty_devices=['spine_router_0_1']; ground truth root_cause_name=['bgp_missing_route_advertisement'], faulty_devices=['leaf_router_0_1'].

**What SADE did differently**

- 19 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → ToolSearch → exec_shell → exec_shell → exec_shell → … (5 more) … → exec_shell → frr_show_running_config → frr_exec → frr_show_running_config → frr_exec → Skill → submit).
- Decisive reasoning (last thinking before `submit`):  
  > The BGP fault skill confirms my diagnosis. The evidence is clear:  **Direct evidence on `leaf_router_0_1`:** - `router bgp 65201` block has **no `network 10.0.1.0/24` statement** for its locally-attached subnet - The prefix `10.0.1.0/24` is absent from all peers' routing tables (confirmed by `leaf_router_0_0` receiving only 30 prefixes instead of 31 from spines) - The advertised-routes output from `leaf_router_0_1` shows no `10.0.1.0/24` entry   - This matches the `bgp_missing_route_advertisement` fingerprint exactly?the router's BGP configuration is missing the network statement for a locally-attached subnet that its peers expect to receive, and the prefix doesn't appear in any peer's routi…

---

## Case 19: `dns_port_blocked` on `dc_clos_service` (l)

**Ground truth.** root_cause_name = `['dns_port_blocked']`, faulty_devices = `['dns_pod2']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0425065311` | 1 | _submitted empty diagnosis_ | empty submission |
| **CC-Baseline** | `0426090029` | 1 | `is_anomaly=True`, `root_cause_name=['bgp_asn_misconfig']`, `faulty_devices=['super_spine_router_0', 'super_spine_router_1', 'super_spine_router_2', 'super_spine_router_3']` | wrong family + wrong device |
| **SADE** | `0429053414` | 5 | `is_anomaly=True`, `root_cause_name=['dns_port_blocked']`, `faulty_devices=['dns_pod2']` | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (16 tool calls). Submitted with empty root_cause_name / faulty_devices.
- **CC-Baseline** (31 tool calls). Submitted root_cause_name=['bgp_asn_misconfig'], faulty_devices=['super_spine_router_0', 'super_spine_router_1', 'super_spine_router_2', 'super_spine_router_3']; ground truth root_cause_name=['dns_port_blocked'], faulty_devices=['dns_pod2'].

**What SADE did differently**

- 11 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → Skill → Bash → Bash → Skill → ToolSearch → exec_shell → ToolSearch → submit).
- Decisive reasoning (last thinking before `submit`):  
  > The output is clear: 1. `named` is running (PID 29, `/usr/sbin/named -f -u bind`) 2. `named` is listening on port 53 (both UDP and TCP on 10.2.0.2:53 and 127.0.0.1:53) 3. The `nft list ruleset` output was truncated but `infra_sweep` already confirmed `tcp dport 53 drop` and `udp dport 53 drop` rules  This is a clear `dns_port_blocked` fault on `dns_pod2`.   I have all the evidence I need: the daemon is running and listening, but nftables rules are dropping all port 53 traffic. I can submit this finding now.

---

## Case 20: `host_ip_conflict` on `ospf_enterprise_static` (m)

**Ground truth.** root_cause_name = `['host_ip_conflict']`, faulty_devices = `['host_2_2_2_1', 'host_1_1_2_2']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0424154241` | 1 | _no submit() call — agent never finalised a diagnosis_ | no submission |
| **CC-Baseline** | `0425133853` | 2 | `is_anomaly=True`, `root_cause_name=['host_ip_conflict']`, `faulty_devices=['host_2_1_2_2']` | wrong device |
| **SADE** | `0426220058` | 4 | `is_anomaly=True`, `root_cause_name=['host_ip_conflict', 'host_incorrect_ip']`, `faulty_devices=['host_1_1_2_2', 'host_2_2_2_1']` | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (46 tool calls). Agent never called `submit()` — exhausted its turn budget without finalising.
- **CC-Baseline** (9 tool calls). Got the fault family right but submitted faulty_devices=['host_2_1_2_2'] (ground truth ['host_1_1_2_2', 'host_2_2_2_1']).

**What SADE did differently**

- 30 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → ToolSearch → exec_shell → exec_shell → exec_shell → … (16 more) … → exec_shell → exec_shell → exec_shell → exec_shell → Skill → ToolSearch → submit).
- Decisive reasoning (last thinking before `submit`):  
  > Now I'll submit the solution. Based on my analysis:  1. `host_1_1_2_2` has IP `10.2.2.4/24` ? should be in 10.1.1.0/24 (wrong IP for its physical subnet) 2. `host_2_2_2_1` also has `10.2.2.4/24` ? correct for its subnet 3. Both share the same IP ? `host_ip_conflict`  The primary root cause is `host_ip_conflict` with both hosts as faulty devices. I could also include `host_incorrect_ip` since `host_1_1_2_2` is clearly on the wrong subnet.   I'm deciding between submitting just `host_ip_conflict` as the root cause since it's the highest-level observable fault and the skill explicitly maps it to both hosts, or including both fault types for comprehensiveness. Since the root cause field can acce…

---

## Case 21: `host_static_blackhole` on `dc_clos_service` (m)

**Ground truth.** root_cause_name = `['host_static_blackhole']`, faulty_devices = `['super_spine_router_1']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0425113117` | 1 | _no submit() call — agent never finalised a diagnosis_ | no submission |
| **CC-Baseline** | `0501112418` | 2 | `is_anomaly=True`, `root_cause_name=['bgp_blackhole_route_leak']`, `faulty_devices=['leaf_router_1_1']` | wrong family + wrong device |
| **SADE** | `0430115411` | 5 | `is_anomaly=True`, `root_cause_name=['host_static_blackhole']`, `faulty_devices=['super_spine_router_1']` | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (29 tool calls). Agent never called `submit()` — exhausted its turn budget without finalising.
- **CC-Baseline** (18 tool calls). Submitted root_cause_name=['bgp_blackhole_route_leak'], faulty_devices=['leaf_router_1_1']; ground truth root_cause_name=['host_static_blackhole'], faulty_devices=['super_spine_router_1'].

**What SADE did differently**

- 19 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → ToolSearch → exec_shell → exec_shell → exec_shell → … (5 more) … → frr_show_ip_route → Skill → Bash → Bash → frr_show_running_config → exec_shell → submit).
- Decisive reasoning (last thinking before `submit`):  
  > …_0 has no route to reach that subnet at all, and super_spine_router_1 should be handling it via its connected interface, but the kernel's blackhole route is blocking the traffic before it can be properly forwarded. When super_spine_router_1 receives that reply packet destined for 192.168.1.2, it hits the blackhole route in its kernel and drops it. This also means super_spine_router_1 never advertises 192.168.1.0/24 to the spine routers via BGP, so super_spine_router_0 has no route to that subnet either?when client_0 tries to ping 192.168.1.2, it gets a destination unreachable error.  The bgp_snapshot flagged both super_spine routers for having zero BGP neighbors, which seemed odd, but looki…

---

## Case 22: `http_acl_block` on `ospf_enterprise_static` (l)

**Ground truth.** root_cause_name = `['http_acl_block']`, faulty_devices = `['host_2_2_4_4']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0425071508` | 1 | `is_anomaly=True`, `root_cause_name=['ospf_area_misconfiguration']`, `faulty_devices=['router_core_1', 'router_core_2', 'router_core_3', 'switch_dist_1_1', 'switch_dist_2_1', 'switch_server_access']` | wrong family + wrong device |
| **CC-Baseline** | `0426095441` | 1 | _no submit() call — agent never finalised a diagnosis_ | no submission |
| **SADE** | `0429060740` | 5 | `is_anomaly=True`, `root_cause_name=['http_acl_block']`, `faulty_devices=['host_2_2_4_4']` | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (27 tool calls). Submitted root_cause_name=['ospf_area_misconfiguration'], faulty_devices=['router_core_1', 'router_core_2', 'router_core_3', 'switch_dist_1_1', 'switch_dist_2_1', 'switch_server_access']; ground truth root_cause_name=['http_acl_block'], faulty_devices=['host_2_2_4_4'].
- **CC-Baseline** (41 tool calls). Agent never called `submit()` — exhausted its turn budget without finalising.

**What SADE did differently**

- 12 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → ToolSearch → Skill → Bash → Skill → Bash → Bash → Skill → ToolSearch → submit).
- Decisive reasoning (last thinking before `submit`):  
  > The `infra_sweep` already showed a TCP port 80 drop rule on `host_2_2_4_4`. The decision table says "TCP port 80 drop rule ? `http_acl_block`". The evidence is direct - the rule was already confirmed by infra_sweep. Let me confirm by checking the actual nft ruleset on that host to be thorough, then submit.  Actually, per the skill instructions: "When direct evidence fully matches a row in the decision table, submit. Do not chain extra probes once the match is complete."  The infra_sweep already showed: - `host_2_2_4_4` has `tcp dport 80 drop` rules (3 of them)   - This maps to `http_acl_block` - Faulty device: `host_2_2_4_4`  I have the answer - time to move to Phase 5 and submit.

---

## Case 23: `http_acl_block` on `ospf_enterprise_static` (s)

**Ground truth.** root_cause_name = `['http_acl_block']`, faulty_devices = `['host_2_1_1_1']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0425070633` | 1 | `is_anomaly=True`, `root_cause_name=['ospf_neighbor_missing']`, `faulty_devices=['switch_dist_1_1', 'switch_dist_2_1']` | wrong family + wrong device |
| **CC-Baseline** | `0426093242` | 1 | _submitted empty diagnosis_ | empty submission |
| **SADE** | `0429055110` | 5 | `is_anomaly=True`, `root_cause_name=['http_acl_block']`, `faulty_devices=['host_2_1_1_1']` | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (49 tool calls). Submitted root_cause_name=['ospf_neighbor_missing'], faulty_devices=['switch_dist_1_1', 'switch_dist_2_1']; ground truth root_cause_name=['http_acl_block'], faulty_devices=['host_2_1_1_1'].
- **CC-Baseline** (60 tool calls). Submitted with empty root_cause_name / faulty_devices.

**What SADE did differently**

- 37 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → ToolSearch → exec_shell → exec_shell → exec_shell → … (23 more) … → exec_shell → exec_shell → exec_shell → exec_shell → exec_shell → ToolSearch → submit).
- Decisive reasoning (last thinking before `submit`):  
  > …nation are just DNS resolution artifacts?the device name itself isn't registered in the local zone, so the harness can't resolve it, but actual IP-based connectivity and HTTP access work fine.  Now I'm parsing through the curl output more carefully. The response shows `000<html>...200`, which is confusing at first, but looking at the command structure with the `&&` and `;` operators, I need to trace through what actually executed and what the status codes mean for each target. the first curl would NOT execute if curl returned non-zero exit code.  Looking at the JSON output again, I'm realizing the `\"` characters are escaped quotes, so the actual raw output has literal `"` characters at the…

---

## Case 24: `http_acl_block` on `rip_small_internet_vpn` (l)

**Ground truth.** root_cause_name = `['http_acl_block']`, faulty_devices = `['host_2']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0425073124` | 1 | `is_anomaly=True`, `root_cause_name=['host_vpn_membership_missing']`, `faulty_devices=['external_router_1', 'host_1']` | wrong family + wrong device |
| **CC-Baseline** | `0426102541` | 1 | `is_anomaly=True`, `root_cause_name=['host_vpn_membership_missing']`, `faulty_devices=['host_1']` | wrong family + wrong device |
| **SADE** | `0429061857` | 5 | `is_anomaly=True`, `root_cause_name=['http_acl_block']`, `faulty_devices=['host_2']` | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (20 tool calls). Submitted root_cause_name=['host_vpn_membership_missing'], faulty_devices=['external_router_1', 'host_1']; ground truth root_cause_name=['http_acl_block'], faulty_devices=['host_2'].
- **CC-Baseline** (37 tool calls). Submitted root_cause_name=['host_vpn_membership_missing'], faulty_devices=['host_1']; ground truth root_cause_name=['http_acl_block'], faulty_devices=['host_2'].

**What SADE did differently**

- 12 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → ToolSearch → Skill → Bash → Bash → Skill → ToolSearch → exec_shell → ToolSearch → submit).
- Decisive reasoning (last thinking before `submit`):  
  > The nft ruleset on host_2 clearly shows:  ``` table inet filter {     chain input {         type filter hook input priority filter; policy accept;         tcp dport 80 drop     }     chain forward {         type filter hook forward priority filter; policy accept;         tcp dport 80 drop     }     chain output {         type filter hook output priority filter; policy accept;         tcp dport 80 drop     } } ```  This is a clear `http_acl_block` fault:   TCP port 80 is being dropped across all three chains, preventing host_2 from receiving, forwarding, or sending HTTP traffic. This matches the decision table exactly, so I'm ready to submit with host_2 as the faulty device and http_acl_block…

---

## Case 25: `icmp_acl_block` on `ospf_enterprise_static` (l)

**Ground truth.** root_cause_name = `['icmp_acl_block']`, faulty_devices = `['host_2_1_2_2']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0425080700` | 1 | _submitted empty diagnosis_ | empty submission |
| **CC-Baseline** | `0426114400` | 1 | _no submit() call — agent never finalised a diagnosis_ | no submission |
| **SADE** | `0429071533` | 5 | `is_anomaly=True`, `root_cause_name=['icmp_acl_block']`, `faulty_devices=['host_2_1_2_2']` | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (39 tool calls). Submitted with empty root_cause_name / faulty_devices.
- **CC-Baseline** (46 tool calls). Agent never called `submit()` — exhausted its turn budget without finalising.

**What SADE did differently**

- 19 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → ToolSearch → Skill → Bash → ToolSearch → … (5 more) … → exec_shell → exec_shell → exec_shell → exec_shell → Skill → ToolSearch → submit).
- Decisive reasoning (last thinking before `submit`):  
  > The acl-skill confirms this is `icmp_acl_block`. The nft ruleset on `host_2_1_2_2` clearly shows ICMP drop rules in all chains. The faulty device is `host_2_1_2_2`.  Let me submit now.

---

## Case 26: `icmp_acl_block` on `ospf_enterprise_static` (s)

**Ground truth.** root_cause_name = `['icmp_acl_block']`, faulty_devices = `['host_1_1_1_1']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0425075604` | 1 | _no submit() call — agent never finalised a diagnosis_ | no submission |
| **CC-Baseline** | `0426112444` | 1 | `is_anomaly=True`, `root_cause_name=['ospf_area_misconfiguration']`, `faulty_devices=['router_core_1', 'router_core_2']` | wrong family + wrong device |
| **SADE** | `0429070157` | 5 | `is_anomaly=True`, `root_cause_name=['icmp_acl_block']`, `faulty_devices=['host_1_1_1_1']` | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (44 tool calls). Agent never called `submit()` — exhausted its turn budget without finalising.
- **CC-Baseline** (33 tool calls). Submitted root_cause_name=['ospf_area_misconfiguration'], faulty_devices=['router_core_1', 'router_core_2']; ground truth root_cause_name=['icmp_acl_block'], faulty_devices=['host_1_1_1_1'].

**What SADE did differently**

- 24 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → ToolSearch → exec_shell → exec_shell → exec_shell → … (10 more) … → exec_shell → Skill → exec_shell → exec_shell → exec_shell → ToolSearch → submit).
- Decisive reasoning (last thinking before `submit`):  
  > Found it! On `host_1_1_1_1`, the nft ruleset has:  ``` table ip filter {     chain input {         type filter hook input priority filter; policy accept;         ip protocol icmp drop     }      chain forward {         type filter hook forward priority filter; policy accept;         ip protocol icmp drop     }      chain output {         type filter hook output priority filter; policy accept;         ip protocol icmp drop     } } ```  ICMP is being dropped on **input**, **forward**, and **output** chains on `host_1_1_1_1`.   This matches the `icmp_acl_block` fingerprint exactly, so `host_1_1_1_1` is the faulty device. I'll verify the root cause name from the available problems and submit the…

---

## Case 27: `icmp_acl_block` on `p4_mpls` (-)

**Ground truth.** root_cause_name = `['icmp_acl_block']`, faulty_devices = `['host_1']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0425085145` | 1 | _submitted empty diagnosis_ | empty submission |
| **CC-Baseline** | `0426131119` | 1 | _no submit() call — agent never finalised a diagnosis_ | no submission |
| **SADE** | `0429085029` | 5 | `is_anomaly=True`, `root_cause_name=['icmp_acl_block']`, `faulty_devices=['host_1']` | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (41 tool calls). Submitted with empty root_cause_name / faulty_devices.
- **CC-Baseline** (47 tool calls). Agent never called `submit()` — exhausted its turn budget without finalising.

**What SADE did differently**

- 36 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → ToolSearch → exec_shell → exec_shell → get_host_net_config → … (22 more) … → bmv2_get_log → bmv2_get_log → exec_shell → exec_shell → exec_shell → ToolSearch → submit).
- Decisive reasoning (last thinking before `submit`):  
  > **FOUND IT!**  In the nft ruleset on host_1:  ``` table ip filter {     chain input {         type filter hook input priority filter; policy accept;         ip protocol icmp drop     }     chain forward {         type filter hook forward priority filter; policy accept;         ip protocol icmp drop     }     chain output {         type filter hook output priority filter; policy accept;         ip protocol icmp drop     } } ```  Host_1 has an nftables rule that **DROPS all ICMP traffic** in all chains (input, forward, output)! This is why:   The nftables rules are blocking ICMP packets from leaving via the output chain and preventing any incoming ICMP replies through the input chain, which is…

---

## Case 28: `incast_traffic_network_limitation` on `dc_clos_service` (l)

**Ground truth.** root_cause_name = `['incast_traffic_network_limitation']`, faulty_devices = `['webserver5_pod1']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0425223501` | 2 | `is_anomaly=True`, `root_cause_name=['link_bandwidth_throttling']`, `faulty_devices=['webserver0_pod0']` | wrong family + wrong device |
| **CC-Baseline** | `0427063825` | 1 | `is_anomaly=True`, `root_cause_name=['host_incorrect_dns']`, `faulty_devices=['client_0', 'client_1', 'client_2', 'client_3']` | wrong family + wrong device |
| **SADE** | `0429194551` | 5 | `is_anomaly=True`, `root_cause_name=['incast_traffic_network_limitation']`, `faulty_devices=['webserver5_pod1']` | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (18 tool calls). Submitted root_cause_name=['link_bandwidth_throttling'], faulty_devices=['webserver0_pod0']; ground truth root_cause_name=['incast_traffic_network_limitation'], faulty_devices=['webserver5_pod1'].
- **CC-Baseline** (34 tool calls). Submitted root_cause_name=['host_incorrect_dns'], faulty_devices=['client_0', 'client_1', 'client_2', 'client_3']; ground truth root_cause_name=['incast_traffic_network_limitation'], faulty_devices=['webserver5_pod1'].

**What SADE did differently**

- 9 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → Skill → ToolSearch → get_tc_statistics → exec_shell → ToolSearch → submit).
- Decisive reasoning (last thinking before `submit`):  
  > The tc qdisc output is definitive:  ``` qdisc netem 1: root refcnt 2 limit 1000 delay 20ms seed 7798523159787514035 qdisc tbf 10: parent 1:1 rate 1Mbit burst 500Kb lat 0us ```  Per the decision table from the skill: - **Root `netem` plus child `tbf` (both present)** ? `incast_traffic_network_limitation`  So the root cause is `incast_traffic_network_limitation` on `webserver5_pod1`.   The 20ms delay from netem combined with the 1Mbit bandwidth cap from tbf explains both the elevated RTT to webserver5_pod3 and the packet loss to webserver3_pod0 when the queue saturates. This matches the decision table, so I'm ready to submit the diagnosis.

---

## Case 29: `incast_traffic_network_limitation` on `dc_clos_service` (s)

**Ground truth.** root_cause_name = `['incast_traffic_network_limitation']`, faulty_devices = `['webserver0_pod0']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0425223024` | 2 | `is_anomaly=True`, `root_cause_name=['link_bandwidth_throttling', 'sender_application_delay']`, `faulty_devices=['webserver0_pod0']` | wrong fault family |
| **CC-Baseline** | `0427062740` | 2 | `is_anomaly=True`, `root_cause_name=['link_bandwidth_throttling']`, `faulty_devices=['webserver0_pod0']` | wrong fault family |
| **SADE** | `0429193216` | 5 | `is_anomaly=True`, `root_cause_name=['incast_traffic_network_limitation']`, `faulty_devices=['webserver0_pod0']` | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (19 tool calls). Got the device right but submitted root_cause_name=['link_bandwidth_throttling', 'sender_application_delay'] (ground truth ['incast_traffic_network_limitation']).
- **CC-Baseline** (26 tool calls). Got the device right but submitted root_cause_name=['link_bandwidth_throttling'] (ground truth ['incast_traffic_network_limitation']).

**What SADE did differently**

- 11 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → Skill → Bash → Bash → Bash → Bash → Skill → ToolSearch → submit).
- Decisive reasoning (last thinking before `submit`):  
  > The tc-fault-skill decision table says: - Root `netem` plus child `tbf` (both present) ? `incast_traffic_network_limitation`  From the tc_snapshot output: ``` qdisc netem 1: dev eth0 root refcnt 2 limit 1000 delay 20ms seed 17642198837053772350 qdisc tbf 10: dev eth0 parent 1:1 rate 1Mbit burst 500Kb lat 0us ```  This is exactly the "Root netem plus child tbf" pattern ? `incast_traffic_network_limitation`.   The faulty device is `webserver0_pod0`, and the tc_snapshot already provides the complete qdisc configuration showing both the root netem and child tbf, which fully matches the decision table row. Since the direct evidence is complete, I can submit the diagnosis without additional probes…

---

## Case 30: `incast_traffic_network_limitation` on `ospf_enterprise_static` (s)

**Ground truth.** root_cause_name = `['incast_traffic_network_limitation']`, faulty_devices = `['web_server_3']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0425223831` | 1 | `is_anomaly=True`, `root_cause_name=['ospf_neighbor_missing']`, `faulty_devices=['switch_dist_1_1', 'switch_dist_2_1']` | wrong family + wrong device |
| **CC-Baseline** | `0427064819` | 1 | `is_anomaly=True`, `root_cause_name=['ospf_area_misconfiguration']`, `faulty_devices=['switch_dist_2_1', 'router_core_2']` | wrong family + wrong device |
| **SADE** | `0429194934` | 5 | `is_anomaly=True`, `root_cause_name=['incast_traffic_network_limitation']`, `faulty_devices=['web_server_3']` | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (38 tool calls). Submitted root_cause_name=['ospf_neighbor_missing'], faulty_devices=['switch_dist_1_1', 'switch_dist_2_1']; ground truth root_cause_name=['incast_traffic_network_limitation'], faulty_devices=['web_server_3'].
- **CC-Baseline** (25 tool calls). Submitted root_cause_name=['ospf_area_misconfiguration'], faulty_devices=['switch_dist_2_1', 'router_core_2']; ground truth root_cause_name=['incast_traffic_network_limitation'], faulty_devices=['web_server_3'].

**What SADE did differently**

- 24 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → ToolSearch → exec_shell → exec_shell → exec_shell → … (10 more) … → exec_shell → exec_shell → exec_shell → exec_shell → Skill → ToolSearch → submit).
- Decisive reasoning (last thinking before `submit`):  
  > I have direct evidence matching the fingerprint. Time to submit now.  - is_anomaly: True (boolean) - root_cause_name: ["incast_traffic_network_limitation"] (list of strings from list_avail_problems) - faulty_devices: ["web_server_3"] (list of strings)

---

## Case 31: `incast_traffic_network_limitation` on `rip_small_internet_vpn` (l)

**Ground truth.** root_cause_name = `['incast_traffic_network_limitation']`, faulty_devices = `['web_server_3_1']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0425230826` | 2 | `is_anomaly=True`, `root_cause_name=['host_vpn_membership_missing', 'link_bandwidth_throttling']`, `faulty_devices=['vpn_server_1', 'gateway_router', 'router1', 'router2', 'external_router_1', 'web_server_1_1']` | wrong family + wrong device |
| **CC-Baseline** | `0427074019` | 2 | `is_anomaly=True`, `root_cause_name=['web_dos_attack']`, `faulty_devices=['host_1', 'host_2', 'host_3', 'host_4', 'host_5', 'host_6', 'host_7', 'host_8', 'web_server_4_7']` | wrong family + wrong device |
| **SADE** | `0429204256` | 5 | `is_anomaly=True`, `root_cause_name=['incast_traffic_network_limitation']`, `faulty_devices=['web_server_3_1']` | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (19 tool calls). Submitted root_cause_name=['host_vpn_membership_missing', 'link_bandwidth_throttling'], faulty_devices=['vpn_server_1', 'gateway_router', 'router1', 'router2', 'external_router_1', 'web_server_1_1']; ground truth root_cause_name=['incast_traffic_network_limitation'], faulty_devices=['web_server_3_1'].
- **CC-Baseline** (24 tool calls). Submitted root_cause_name=['web_dos_attack'], faulty_devices=['host_1', 'host_2', 'host_3', 'host_4', 'host_5', 'host_6', 'host_7', 'host_8', 'web_server_4_7']; ground truth root_cause_name=['incast_traffic_network_limitation'], faulty_devices=['web_server_3_1'].

**What SADE did differently**

- 39 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → ToolSearch → Skill → exec_shell → exec_shell → … (25 more) … → exec_shell → exec_shell → exec_shell → exec_shell → exec_shell → ToolSearch → submit).
- Decisive reasoning (last thinking before `submit`):  
  > …_network_limitation with web_server_3_1 as the faulty device, high confidence, and is_anomaly as true. The tc rule is isolated to web_server_3_1 while all other devices are clean. The decision table confirms that root netem plus child tbf together point directly to incast_traffic_network_limitation. I've confirmed the root cause is `incast_traffic_network_limitation` on web_server_3_1, and I'm now organizing the findings into a comprehensive troubleshooting report that documents the TC fault configuration, the cascading effects it creates, and how the incast congestion manifests across the network path. RTT (100-270ms) from all web_server_3_x hosts to external destinations during simultaneo…

---

## Case 32: `incast_traffic_network_limitation` on `rip_small_internet_vpn` (s)

**Ground truth.** root_cause_name = `['incast_traffic_network_limitation']`, faulty_devices = `['web_server_1_1']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0425225237` | 2 | `is_anomaly=True`, `root_cause_name=['link_bandwidth_throttling']`, `faulty_devices=['external_router_1']` | wrong family + wrong device |
| **CC-Baseline** | `0427072824` | 2 | `is_anomaly=True`, `root_cause_name=['link_bandwidth_throttling']`, `faulty_devices=['web_server_1_2']` | wrong family + wrong device |
| **SADE** | `0429202239` | 5 | `is_anomaly=True`, `root_cause_name=['incast_traffic_network_limitation']`, `faulty_devices=['web_server_1_1']` | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (42 tool calls). Submitted root_cause_name=['link_bandwidth_throttling'], faulty_devices=['external_router_1']; ground truth root_cause_name=['incast_traffic_network_limitation'], faulty_devices=['web_server_1_1'].
- **CC-Baseline** (36 tool calls). Submitted root_cause_name=['link_bandwidth_throttling'], faulty_devices=['web_server_1_2']; ground truth root_cause_name=['incast_traffic_network_limitation'], faulty_devices=['web_server_1_1'].

**What SADE did differently**

- 9 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → Skill → Skill → Bash → Bash → ToolSearch → submit).
- Decisive reasoning (last thinking before `submit`):  
  > Now let me submit the solution.

---

## Case 33: `link_bandwidth_throttling` on `dc_clos_service` (l)

**Ground truth.** root_cause_name = `['link_bandwidth_throttling']`, faulty_devices = `['client_1']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0425233306` | 1 | _submitted empty diagnosis_ | empty submission |
| **CC-Baseline** | `0427083119` | 2 | `is_anomaly=True`, `root_cause_name=['host_incorrect_dns']`, `faulty_devices=['client_3']` | wrong family + wrong device |
| **SADE** | `0429212540` | 4 | _no submit() call — agent never finalised a diagnosis_ | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (21 tool calls). Submitted with empty root_cause_name / faulty_devices.
- **CC-Baseline** (35 tool calls). Submitted root_cause_name=['host_incorrect_dns'], faulty_devices=['client_3']; ground truth root_cause_name=['link_bandwidth_throttling'], faulty_devices=['client_1'].

**What SADE did differently**

- 35 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → Skill → Bash → Bash → Bash → … (21 more) … → exec_shell → exec_shell → exec_shell → exec_shell → exec_shell → exec_shell → ToolSearch).
- Decisive reasoning (last thinking before `submit`):  
  > …planation is that service_snapshot doesn't use `--resolve` for pod3's HTTP test and instead relies on DNS, which fails, causing the HTTP failure. For pod0 and pod1, service_snapshot might have a separate topology knowledge base that provides the expected IPs for `--resolve`, independent of the live DNS test results?that would explain why the HTTP tests succeed even though the DNS tests fail.  Pod3's expected_remote IP is correctly specified as 10.3.1.2 in the output, so the issue isn't a missing topology entry. At this point, I'm moving forward with what I've confirmed: pod3's webservers are running and reachable via direct IP, DNS resolution fails due to the glibc MAXNS limitation, and the…

---

## Case 34: `link_bandwidth_throttling` on `ospf_enterprise_static` (l)

**Ground truth.** root_cause_name = `['link_bandwidth_throttling']`, faulty_devices = `['host_1_1_1_1']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0425234632` | 1 | `is_anomaly=True`, `root_cause_name=['ospf_area_misconfiguration']`, `faulty_devices=['router_core_1', 'router_core_2', 'router_core_3', 'switch_dist_1_1', 'switch_dist_2_1', 'switch_server_access']` | wrong family + wrong device |
| **CC-Baseline** | `0427085251` | 1 | _no submit() call — agent never finalised a diagnosis_ | no submission |
| **SADE** | `0429222204` | 5 | `is_anomaly=True`, `root_cause_name=['link_bandwidth_throttling']`, `faulty_devices=['host_1_1_1_1']` | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (40 tool calls). Submitted root_cause_name=['ospf_area_misconfiguration'], faulty_devices=['router_core_1', 'router_core_2', 'router_core_3', 'switch_dist_1_1', 'switch_dist_2_1', 'switch_server_access']; ground truth root_cause_name=['link_bandwidth_throttling'], faulty_devices=['host_1_1_1_1'].
- **CC-Baseline** (37 tool calls). Agent never called `submit()` — exhausted its turn budget without finalising.

**What SADE did differently**

- 25 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → Skill → Bash → ToolSearch → exec_shell → … (11 more) … → exec_shell → exec_shell → exec_shell → exec_shell → Skill → ToolSearch → submit).
- Decisive reasoning (last thinking before `submit`):  
  > The tc-fault-skill confirms: - Root `tbf` only ? `link_bandwidth_throttling` - Faulty device: `host_1_1_1_1`  The decision table matches: `host_1_1_1_1 eth0` has root `tbf` only ? `link_bandwidth_throttling`.  Now I'll submit the result.

---

## Case 35: `link_bandwidth_throttling` on `rip_small_internet_vpn` (m)

**Ground truth.** root_cause_name = `['link_bandwidth_throttling']`, faulty_devices = `['host_1']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0426000033` | 1 | _submitted empty diagnosis_ | empty submission |
| **CC-Baseline** | `0427091816` | 2 | `is_anomaly=True`, `root_cause_name=['incast_traffic_network_limitation']`, `faulty_devices=['host_2']` | wrong family + wrong device |
| **SADE** | `0429224641` | 5 | `is_anomaly=True`, `root_cause_name=['link_bandwidth_throttling']`, `faulty_devices=['host_1']` | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (35 tool calls). Submitted with empty root_cause_name / faulty_devices.
- **CC-Baseline** (37 tool calls). Submitted root_cause_name=['incast_traffic_network_limitation'], faulty_devices=['host_2']; ground truth root_cause_name=['link_bandwidth_throttling'], faulty_devices=['host_1'].

**What SADE did differently**

- 18 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → Skill → Skill → Bash → Bash → … (4 more) … → exec_shell → exec_shell → exec_shell → exec_shell → exec_shell → ToolSearch → submit).
- Decisive reasoning (last thinking before `submit`):  
  > Now let me submit. The confirmed fault is `link_bandwidth_throttling` on `host_1`. The decision table in tc-fault-skill says "Root `tbf` only ? `link_bandwidth_throttling`".  - `is_anomaly`: True - `root_cause_name`: ["link_bandwidth_throttling"] - `faulty_devices`: ["host_1"]

---

## Case 36: `link_detach` on `ospf_enterprise_static` (l)

**Ground truth.** root_cause_name = `['link_detach']`, faulty_devices = `['host_2_1_4_2']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0424223108` | 2 | `is_anomaly=True`, `root_cause_name=['host_missing_ip']`, `faulty_devices=['host_1_1_1_1']` | wrong family + wrong device |
| **CC-Baseline** | `0425211846` | 1 | _no submit() call — agent never finalised a diagnosis_ | no submission |
| **SADE** | `0427080938` | 5 | `is_anomaly=True`, `root_cause_name=['link_detach']`, `faulty_devices=['host_2_1_4_2']` | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (18 tool calls). Submitted root_cause_name=['host_missing_ip'], faulty_devices=['host_1_1_1_1']; ground truth root_cause_name=['link_detach'], faulty_devices=['host_2_1_4_2'].
- **CC-Baseline** (42 tool calls). Agent never called `submit()` — exhausted its turn budget without finalising.

**What SADE did differently**

- 13 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → Skill → Bash → ToolSearch → exec_shell → get_host_net_config → get_host_net_config → Skill → exec_shell → ToolSearch → submit).
- Decisive reasoning (last thinking before `submit`):  
  > `ip link show` confirms that only the loopback interface is present on `host_2_1_4_2`. There is no eth0. This directly matches the fingerprint: - "Interface missing from `ip link show`" ? `link_detach`  Faulty device: `host_2_1_4_2`  Now I'll proceed to Phase 5 ? submission. The root_cause_name is `link_detach`, faulty_devices is `["host_2_1_4_2"]`.

---

## Case 37: `link_detach` on `ospf_enterprise_static` (m)

**Ground truth.** root_cause_name = `['link_detach']`, faulty_devices = `['host_2_2_2_2']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0424222429` | 1 | _no submit() call — agent never finalised a diagnosis_ | no submission |
| **CC-Baseline** | `0425211023` | 2 | `is_anomaly=True`, `root_cause_name=['host_missing_ip']`, `faulty_devices=['host_2_1_1_2']` | wrong family + wrong device |
| **SADE** | `0427080107` | 5 | `is_anomaly=True`, `root_cause_name=['link_detach']`, `faulty_devices=['host_2_2_2_2']` | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (49 tool calls). Agent never called `submit()` — exhausted its turn budget without finalising.
- **CC-Baseline** (33 tool calls). Submitted root_cause_name=['host_missing_ip'], faulty_devices=['host_2_1_1_2']; ground truth root_cause_name=['link_detach'], faulty_devices=['host_2_2_2_2'].

**What SADE did differently**

- 20 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → ToolSearch → exec_shell → exec_shell → exec_shell → … (6 more) … → Skill → Bash → exec_shell → Bash → Skill → Bash → submit).
- Decisive reasoning (last thinking before `submit`):  
  > The infra_sweep for routers and servers returned no flags. Everything is clean except for `host_2_2_2_2`.  Now let me proceed to Phase 5 ? Submission.  Summary: - Root cause: `link_detach` on `host_2_2_2_2` - Evidence: eth0 completely absent from `ip link show`, only loopback present - Confirmed: Only 1 faulty device across all 16 hosts, 8 routers, 5 servers   - Confidence is very high, so I'm ready to submit.

---

## Case 38: `link_flap` on `dc_clos_bgp` (s)

**Ground truth.** root_cause_name = `['link_flap']`, faulty_devices = `['pc_0_1']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0425005107` | 2 | `is_anomaly=True`, `root_cause_name=['host_incorrect_gateway']`, `faulty_devices=['pc_0_1']` | wrong fault family |
| **CC-Baseline** | `0425234652` | 2 | `is_anomaly=True`, `root_cause_name=['host_incorrect_gateway']`, `faulty_devices=['pc_0_0']` | wrong family + wrong device |
| **SADE** | `0427114915` | 5 | `is_anomaly=True`, `root_cause_name=['link_flap']`, `faulty_devices=['pc_0_1']` | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (25 tool calls). Got the device right but submitted root_cause_name=['host_incorrect_gateway'] (ground truth ['link_flap']).
- **CC-Baseline** (19 tool calls). Submitted root_cause_name=['host_incorrect_gateway'], faulty_devices=['pc_0_0']; ground truth root_cause_name=['link_flap'], faulty_devices=['pc_0_1'].

**What SADE did differently**

- 16 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → ToolSearch → exec_shell → exec_shell → Skill → … (2 more) … → exec_shell → exec_shell → Skill → exec_shell → exec_shell → ToolSearch → submit).
- Decisive reasoning (last thinking before `submit`):  
  > I have direct evidence matching the `link_flap` fingerprint. I should submit now.  Let me confirm the submit signature from CLAUDE.md: `submit(is_anomaly: bool, root_cause_name: list[str], faulty_devices: list[str], confidence: float, summary: str)`  Wait, the submit tool schema shows: - `is_anomaly`: bool - `faulty_devices`: list[str] - `root_cause_name`: list[str]  No `confidence` or `summary` in the required parameters. Let me just submit with the required parameters.

---

## Case 39: `link_flap` on `dc_clos_service` (l)

**Ground truth.** root_cause_name = `['link_flap']`, faulty_devices = `['client_0']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0425011728` | 2 | `is_anomaly=True`, `root_cause_name=['host_incorrect_gateway', 'link_down']`, `faulty_devices=['client_0']` | wrong fault family |
| **CC-Baseline** | `0426002219` | 1 | `is_anomaly=True`, `root_cause_name=['host_incorrect_gateway']`, `faulty_devices=['client_3']` | wrong family + wrong device |
| **SADE** | `0427121227` | 5 | `is_anomaly=True`, `root_cause_name=['link_flap']`, `faulty_devices=['client_0']` | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (14 tool calls). Got the device right but submitted root_cause_name=['host_incorrect_gateway', 'link_down'] (ground truth ['link_flap']).
- **CC-Baseline** (17 tool calls). Submitted root_cause_name=['host_incorrect_gateway'], faulty_devices=['client_3']; ground truth root_cause_name=['link_flap'], faulty_devices=['client_0'].

**What SADE did differently**

- 11 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → ToolSearch → exec_shell → exec_shell → Skill → exec_shell → Skill → ToolSearch → submit).
- Decisive reasoning (last thinking before `submit`):  
  > The link-fault-skill is now loaded. Looking at the decision table:  | Interface is UP now, but flap script/process is present and the host is in a transient DHCP or no-route window | `link_flap` |  `client_0` has: - `eth0` is currently UP  - `/tmp/link_flap.sh` and `/tmp/link_flap.pid` exist - Active process: `bash /tmp/link_flap.sh eth0 1 1` is running - Direct-IP pings from `client_0` failed with "Network is unreachable" (no-route window)   - This matches the `link_flap` condition perfectly?the interface is up but the flap script is running and the host can't reach the network. I'll submit `client_0` as the faulty device with `link_flap` as the root cause.

---

## Case 40: `link_flap` on `dc_clos_service` (m)

**Ground truth.** root_cause_name = `['link_flap']`, faulty_devices = `['client_1']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0425011117` | 2 | `is_anomaly=True`, `root_cause_name=['host_incorrect_gateway']`, `faulty_devices=['client_0']` | wrong family + wrong device |
| **CC-Baseline** | `0426001543` | 2 | `is_anomaly=True`, `root_cause_name=['host_incorrect_gateway']`, `faulty_devices=['client_1']` | wrong fault family |
| **SADE** | `0427120821` | 5 | `is_anomaly=True`, `root_cause_name=['link_flap']`, `faulty_devices=['client_1']` | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (28 tool calls). Submitted root_cause_name=['host_incorrect_gateway'], faulty_devices=['client_0']; ground truth root_cause_name=['link_flap'], faulty_devices=['client_1'].
- **CC-Baseline** (13 tool calls). Got the device right but submitted root_cause_name=['host_incorrect_gateway'] (ground truth ['link_flap']).

**What SADE did differently**

- 11 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → ToolSearch → exec_shell → exec_shell → Skill → exec_shell → Skill → ToolSearch → submit).
- Decisive reasoning (last thinking before `submit`):  
  > Now I'll submit the result. The root cause is `link_flap`, the faulty device is `client_1`, and it is an anomaly.

---

## Case 41: `link_flap` on `ospf_enterprise_static` (l)

**Ground truth.** root_cause_name = `['link_flap']`, faulty_devices = `['host_1_1_4_2']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0425013302` | 2 | _no submit() call — agent never finalised a diagnosis_ | no submission |
| **CC-Baseline** | `0426004653` | 1 | _no submit() call — agent never finalised a diagnosis_ | no submission |
| **SADE** | `0427123043` | 5 | `is_anomaly=True`, `root_cause_name=['link_flap']`, `faulty_devices=['host_1_1_4_2']` | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (21 tool calls). Agent never called `submit()` — exhausted its turn budget without finalising.
- **CC-Baseline** (40 tool calls). Agent never called `submit()` — exhausted its turn budget without finalising.

**What SADE did differently**

- 13 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → Skill → Bash → ToolSearch → exec_shell → exec_shell → Skill → exec_shell → Skill → ToolSearch → submit).
- Decisive reasoning (last thinking before `submit`):  
  > The link-fault-skill decision table is clear. The evidence already gathered matches the fingerprint exactly:  - Interface `eth0` is currently **UP** (from the pre-entry gate) - Flap script/process IS present: `/tmp/link_flap.sh`, `/tmp/link_flap.pid`, process `/bin/bash /tmp/link_flap.sh eth0 1 1` running - The host is in a transient no-route window (direct-IP pings return "Network is unreachable")  This matches: "Interface is UP now, but flap script/process is present and the host is in a transient DHCP or no-route window ? `link_flap`"   I've identified the faulty device as `host_1_1_4_2` with complete evidence supporting the diagnosis, so I'm ready to submit the result.

---

## Case 42: `link_flap` on `rip_small_internet_vpn` (m)

**Ground truth.** root_cause_name = `['link_flap']`, faulty_devices = `['host_3']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0425014012` | 2 | `is_anomaly=True`, `root_cause_name=['link_down', 'flow_rule_shadowing']`, `faulty_devices=['host_2', 'external_router_1']` | wrong family + wrong device |
| **CC-Baseline** | `0426005746` | 2 | `is_anomaly=True`, `root_cause_name=['link_down']`, `faulty_devices=['host_4']` | wrong family + wrong device |
| **SADE** | `0427123825` | 5 | `is_anomaly=True`, `root_cause_name=['link_flap']`, `faulty_devices=['host_3']` | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (42 tool calls). Submitted root_cause_name=['link_down', 'flow_rule_shadowing'], faulty_devices=['host_2', 'external_router_1']; ground truth root_cause_name=['link_flap'], faulty_devices=['host_3'].
- **CC-Baseline** (13 tool calls). Submitted root_cause_name=['link_down'], faulty_devices=['host_4']; ground truth root_cause_name=['link_flap'], faulty_devices=['host_3'].

**What SADE did differently**

- 9 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → ToolSearch → exec_shell → Skill → exec_shell → Skill → submit).
- Decisive reasoning (last thinking before `submit`):  
  > The evidence already perfectly matches the decision table:  - Interface `eth0` is **DOWN** (from `ip link show`) - Flap script/process is present: `/tmp/link_flap.sh`, `/tmp/link_flap.pid`, and `link_flap.sh eth0 1 1` is actively running  Decision table row: "Interface is DOWN and flap script/process is present ? `link_flap`"  Faulty device: `host_3`  Now I should submit with: - `is_anomaly`: True - `root_cause_name`: ["link_flap"]   - `faulty_devices`: ["host_3"] - `confidence`: 0.98 (very high, all three signals fire)  Let me submit.

---

## Case 43: `link_fragmentation_disabled` on `dc_clos_bgp` (l)

**Ground truth.** root_cause_name = `['link_fragmentation_disabled']`, faulty_devices = `['pc_1_3']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0425024651` | 2 | `is_anomaly=True`, `root_cause_name=['arp_acl_block']`, `faulty_devices=['pc_0_0']` | wrong family + wrong device |
| **CC-Baseline** | `0426022600` | 2 | `is_anomaly=True`, `root_cause_name=['icmp_acl_block']`, `faulty_devices=['pc_3_7']` | wrong family + wrong device |
| **SADE** | `0427143459` | 5 | `is_anomaly=True`, `root_cause_name=['link_fragmentation_disabled']`, `faulty_devices=['pc_1_3']` | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (21 tool calls). Submitted root_cause_name=['arp_acl_block'], faulty_devices=['pc_0_0']; ground truth root_cause_name=['link_fragmentation_disabled'], faulty_devices=['pc_1_3'].
- **CC-Baseline** (20 tool calls). Submitted root_cause_name=['icmp_acl_block'], faulty_devices=['pc_3_7']; ground truth root_cause_name=['link_fragmentation_disabled'], faulty_devices=['pc_1_3'].

**What SADE did differently**

- 20 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → ToolSearch → exec_shell → exec_shell → exec_shell → … (6 more) … → exec_shell → exec_shell → exec_shell → exec_shell → exec_shell → ToolSearch → submit).
- Decisive reasoning (last thinking before `submit`):  
  > …ptables output, the INPUT chain is empty with ACCEPT policy, so incoming packets should be allowed. The issue is purely the OUTPUT rule dropping packets between 10-65535 bytes. ARP traffic bypasses iptables entirely since it operates at layer 2, which is why the router can still see pc_1_3's MAC address, but ICMP replies from pc_1_3 are being blocked by the OUTPUT rule. The iptables rule drops all packets between 10-65535 bytes, which catches the 84-byte PING packets. According to the fault index, this packet-length filter points to the `acl-skill` family with the `link_fragmentation_disabled` fault on `pc_1_3`. I should enter the skill to confirm and submit efficiently. as an iptables leng…

---

## Case 44: `link_fragmentation_disabled` on `dc_clos_bgp` (m)

**Ground truth.** root_cause_name = `['link_fragmentation_disabled']`, faulty_devices = `['pc_0_3']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0425024155` | 1 | _no submit() call — agent never finalised a diagnosis_ | no submission |
| **CC-Baseline** | `0426021446` | 2 | `is_anomaly=True`, `root_cause_name=['icmp_acl_block']`, `faulty_devices=['pc_0_3']` | wrong fault family |
| **SADE** | `0427142611` | 5 | `is_anomaly=True`, `root_cause_name=['link_fragmentation_disabled']`, `faulty_devices=['pc_0_3']` | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (39 tool calls). Agent never called `submit()` — exhausted its turn budget without finalising.
- **CC-Baseline** (21 tool calls). Got the device right but submitted root_cause_name=['icmp_acl_block'] (ground truth ['link_fragmentation_disabled']).

**What SADE did differently**

- 23 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → ToolSearch → exec_shell → exec_shell → Skill → … (9 more) … → exec_shell → exec_shell → exec_shell → exec_shell → Skill → ToolSearch → submit).
- Decisive reasoning (last thinking before `submit`):  
  > The acl-skill confirms:  Fingerprint: `iptables length-based DROP rule` ? Submit as `link_fragmentation_disabled`  The faulty device is `pc_0_3` (it owns the matching drop rule in its OUTPUT chain).  Direct evidence: - `pc_0_3` iptables OUTPUT chain: `DROP 0 -- * * 0.0.0.0/0 0.0.0.0/0 length 10:65535` - This is an iptables length-based DROP rule - This matches the fingerprint exactly ? `link_fragmentation_disabled`   - Now I'm ready to submit with `pc_0_3` as the faulty device.

---

## Case 45: `link_fragmentation_disabled` on `dc_clos_bgp` (s)

**Ground truth.** root_cause_name = `['link_fragmentation_disabled']`, faulty_devices = `['pc_0_0']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0425023812` | 2 | `is_anomaly=True`, `root_cause_name=['icmp_acl_block']`, `faulty_devices=['pc_0_0']` | wrong fault family |
| **CC-Baseline** | `0426020210` | 1 | `is_anomaly=True`, `root_cause_name=['icmp_acl_block']`, `faulty_devices=['pc_0_1']` | wrong family + wrong device |
| **SADE** | `0427141858` | 5 | `is_anomaly=True`, `root_cause_name=['link_fragmentation_disabled']`, `faulty_devices=['pc_0_0']` | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (35 tool calls). Got the device right but submitted root_cause_name=['icmp_acl_block'] (ground truth ['link_fragmentation_disabled']).
- **CC-Baseline** (45 tool calls). Submitted root_cause_name=['icmp_acl_block'], faulty_devices=['pc_0_1']; ground truth root_cause_name=['link_fragmentation_disabled'], faulty_devices=['pc_0_0'].

**What SADE did differently**

- 26 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → ToolSearch → exec_shell → exec_shell → Skill → … (12 more) … → exec_shell → exec_shell → exec_shell → exec_shell → exec_shell → ToolSearch → submit).
- Decisive reasoning (last thinking before `submit`):  
  > Excellent! Now I found the issue!  On pc_0_0: ``` Chain OUTPUT (policy ACCEPT) DROP       0    --  0.0.0.0/0            0.0.0.0/0            length 10:65535 ```  There's an iptables OUTPUT rule on pc_0_0 that drops ALL packets with a size between 10 and 65535 bytes! This would drop essentially all outgoing packets (ICMP ping packets are at least 84 bytes). This is why:   - Pings from pc_0_0 to pc_0_1 fail because all outgoing traffic gets dropped - Pings from leaf_router_0_0 to pc_0_0 fail because pc_0_0 receives the ping but drops the reply when trying to send it out  The ARP entries confirm pc_0_0 has the correct MAC address for leaf_router_0_0, so the connectivity issue is purely this OUT…

---

## Case 46: `link_fragmentation_disabled` on `dc_clos_service` (l)

**Ground truth.** root_cause_name = `['link_fragmentation_disabled']`, faulty_devices = `['client_1']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0425030836` | 1 | `is_anomaly=True`, `root_cause_name=['host_incorrect_ip', 'dns_service_down']`, `faulty_devices=['super_spine_router_0', 'dns_pod0']` | wrong family + wrong device |
| **CC-Baseline** | `0426025108` | 2 | `is_anomaly=True`, `root_cause_name=['icmp_acl_block']`, `faulty_devices=['client_0']` | wrong family + wrong device |
| **SADE** | `0427145642` | 5 | `is_anomaly=True`, `root_cause_name=['link_fragmentation_disabled']`, `faulty_devices=['client_1']` | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (23 tool calls). Submitted root_cause_name=['host_incorrect_ip', 'dns_service_down'], faulty_devices=['super_spine_router_0', 'dns_pod0']; ground truth root_cause_name=['link_fragmentation_disabled'], faulty_devices=['client_1'].
- **CC-Baseline** (25 tool calls). Submitted root_cause_name=['icmp_acl_block'], faulty_devices=['client_0']; ground truth root_cause_name=['link_fragmentation_disabled'], faulty_devices=['client_1'].

**What SADE did differently**

- 18 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → ToolSearch → exec_shell → exec_shell → exec_shell → … (4 more) … → exec_shell → exec_shell → exec_shell → exec_shell → Skill → ToolSearch → submit).
- Decisive reasoning (last thinking before `submit`):  
  > The acl-skill confirms this perfectly. I found an `iptables length-based DROP rule` on `client_1`: ``` DROP  0  --  *  *  0.0.0.0/0  0.0.0.0/0  length 10:65535 ```  Per the decision table: - "iptables length-based DROP rule" ? `link_fragmentation_disabled`  The faulty device is `client_1` (owns the matching drop rule).  Now let me submit.

---

## Case 47: `link_fragmentation_disabled` on `dc_clos_service` (s)

**Ground truth.** root_cause_name = `['link_fragmentation_disabled']`, faulty_devices = `['client_0']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0425025312` | 1 | `is_anomaly=True`, `root_cause_name=['icmp_acl_block', 'dns_port_blocked', 'http_acl_block']`, `faulty_devices=['client_0']` | wrong fault family |
| **CC-Baseline** | `0426023505` | 2 | `is_anomaly=True`, `root_cause_name=['icmp_acl_block']`, `faulty_devices=['client_0']` | wrong fault family |
| **SADE** | `0427144233` | 5 | `is_anomaly=True`, `root_cause_name=['link_fragmentation_disabled']`, `faulty_devices=['client_0']` | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (48 tool calls). Got the device right but submitted root_cause_name=['icmp_acl_block', 'dns_port_blocked', 'http_acl_block'] (ground truth ['link_fragmentation_disabled']).
- **CC-Baseline** (27 tool calls). Got the device right but submitted root_cause_name=['icmp_acl_block'] (ground truth ['link_fragmentation_disabled']).

**What SADE did differently**

- 23 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → ToolSearch → exec_shell → exec_shell → exec_shell → … (9 more) … → exec_shell → exec_shell → exec_shell → exec_shell → Skill → ToolSearch → submit).
- Decisive reasoning (last thinking before `submit`):  
  > I have direct evidence on the owning device matching the fault-family fingerprint. Submitting now.

---

## Case 48: `link_fragmentation_disabled` on `ospf_enterprise_static` (l)

**Ground truth.** root_cause_name = `['link_fragmentation_disabled']`, faulty_devices = `['host_1_1_2_4']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0425033030` | 2 | `is_anomaly=True`, `root_cause_name=['host_static_blackhole']`, `faulty_devices=['host_1_1_1_1']` | wrong family + wrong device |
| **CC-Baseline** | `0426031449` | 1 | _no submit() call — agent never finalised a diagnosis_ | no submission |
| **SADE** | `0427151557` | 5 | `is_anomaly=True`, `root_cause_name=['link_fragmentation_disabled']`, `faulty_devices=['host_1_1_2_4']` | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (40 tool calls). Submitted root_cause_name=['host_static_blackhole'], faulty_devices=['host_1_1_1_1']; ground truth root_cause_name=['link_fragmentation_disabled'], faulty_devices=['host_1_1_2_4'].
- **CC-Baseline** (35 tool calls). Agent never called `submit()` — exhausted its turn budget without finalising.

**What SADE did differently**

- 28 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → Skill → Bash → ToolSearch → exec_shell → … (14 more) … → exec_shell → exec_shell → exec_shell → exec_shell → Skill → ToolSearch → submit).
- Decisive reasoning (last thinking before `submit`):  
  > The acl-skill confirms the decision table:  | Fingerprint in ruleset | Submit | |---|---| | iptables length-based DROP rule | `link_fragmentation_disabled` |  The iptables OUTPUT chain on `host_1_1_2_4` has: ``` DROP  0  --  *  *  0.0.0.0/0  0.0.0.0/0  length 10:65535 ```  This is an iptables length-based DROP rule ? `link_fragmentation_disabled`.   I've identified `host_1_1_2_4` as the faulty device with this matching drop rule, so I'm submitting the anomaly with high confidence?the host has an iptables rule blocking all outbound packets between 10 and 65535 bytes in length.

---

## Case 49: `link_fragmentation_disabled` on `ospf_enterprise_static` (m)

**Ground truth.** root_cause_name = `['link_fragmentation_disabled']`, faulty_devices = `['host_2_2_1_2']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0425032153` | 1 | _no submit() call — agent never finalised a diagnosis_ | no submission |
| **CC-Baseline** | `0426030522` | 1 | _no submit() call — agent never finalised a diagnosis_ | no submission |
| **SADE** | `0427150828` | 5 | `is_anomaly=True`, `root_cause_name=['link_fragmentation_disabled']`, `faulty_devices=['host_2_2_1_2']` | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (48 tool calls). Agent never called `submit()` — exhausted its turn budget without finalising.
- **CC-Baseline** (56 tool calls). Agent never called `submit()` — exhausted its turn budget without finalising.

**What SADE did differently**

- 27 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → ToolSearch → exec_shell → exec_shell → exec_shell → … (13 more) … → exec_shell → Skill → Bash → Bash → Skill → ToolSearch → submit).
- Decisive reasoning (last thinking before `submit`):  
  > …ear:  - **iptables length-based DROP rule** on `host_2_2_1_2` ? `link_fragmentation_disabled` - Faulty device: `host_2_2_1_2`  Per the decision table: "iptables length-based DROP rule ? `link_fragmentation_disabled`"  The rule `-A OUTPUT -m length --length 10:65535 -j DROP` is a direct match. This is direct evidence on the owning device matching the fault-family fingerprint.  Per the instructions: "When direct evidence fully matches a row in the decision table, submit. Do not chain extra probes once the match is complete."   Now I'm preparing the submission with the parameters: anomaly confirmed, root cause identified as link fragmentation disabled, faulty device pinpointed as host_2_2_1_2,…

---

## Case 50: `link_fragmentation_disabled` on `ospf_enterprise_static` (s)

**Ground truth.** root_cause_name = `['link_fragmentation_disabled']`, faulty_devices = `['host_2_1_1_1']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0425031407` | 2 | `is_anomaly=True`, `root_cause_name=['icmp_acl_block']`, `faulty_devices=['host_2_1_1_1']` | wrong fault family |
| **CC-Baseline** | `0426025821` | 2 | `is_anomaly=True`, `root_cause_name=['icmp_acl_block']`, `faulty_devices=['host_1_1_1_1']` | wrong family + wrong device |
| **SADE** | `0427150209` | 5 | `is_anomaly=True`, `root_cause_name=['link_fragmentation_disabled']`, `faulty_devices=['host_2_1_1_1']` | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (48 tool calls). Got the device right but submitted root_cause_name=['icmp_acl_block'] (ground truth ['link_fragmentation_disabled']).
- **CC-Baseline** (37 tool calls). Submitted root_cause_name=['icmp_acl_block'], faulty_devices=['host_1_1_1_1']; ground truth root_cause_name=['link_fragmentation_disabled'], faulty_devices=['host_2_1_1_1'].

**What SADE did differently**

- 26 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → ToolSearch → exec_shell → exec_shell → exec_shell → … (12 more) … → exec_shell → exec_shell → exec_shell → exec_shell → exec_shell → ToolSearch → submit).
- Decisive reasoning (last thinking before `submit`):  
  > …s like web0.local and web1.local, so container names like `host_1_1_1_1` aren't resolvable?that's expected. The "Got recursion not available" message from host_1_1_1_1 is just a warning when trying to resolve names outside the local zone, but the DNS service itself is functioning properly. The only actual fault I'm seeing is `link_fragmentation_disabled` on `host_2_1_1_1`. I haven't verified those other web server records yet, but given the reachability data and my direct IP tests, the real issue is clear: host_2_1_1_1 is completely isolated with no connectivity. With only 10 API turns left, I should move forward with submitting my findings rather than exhausting the remaining calls on DNS …

---

## Case 51: `link_fragmentation_disabled` on `p4_bloom_filter` (-)

**Ground truth.** root_cause_name = `['link_fragmentation_disabled']`, faulty_devices = `['host_2']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0425042629` | 2 | `is_anomaly=True`, `root_cause_name=['icmp_acl_block']`, `faulty_devices=['host_2']` | wrong fault family |
| **CC-Baseline** | `0426041157` | 2 | _no submit() call — agent never finalised a diagnosis_ | no submission |
| **SADE** | `0430152004` | 5 | `is_anomaly=True`, `root_cause_name=['link_fragmentation_disabled']`, `faulty_devices=['host_2']` | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (28 tool calls). Got the device right but submitted root_cause_name=['icmp_acl_block'] (ground truth ['link_fragmentation_disabled']).
- **CC-Baseline** (43 tool calls). Agent never called `submit()` — exhausted its turn budget without finalising.

**What SADE did differently**

- 35 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → ToolSearch → exec_shell → exec_shell → exec_shell → … (21 more) … → exec_shell → bmv2_get_log → exec_shell → exec_shell → Skill → ToolSearch → submit).
- Decisive reasoning (last thinking before `submit`):  
  > The acl-skill decision table confirms:  | Fingerprint in ruleset | Submit | |---|---| | iptables length-based DROP rule | `link_fragmentation_disabled` |  And I have direct evidence: - host_2 OUTPUT chain has: `DROP 0 -- * * 0.0.0.0/0 0.0.0.0/0 length 10:65535` - This is an iptables length-based DROP rule ? `link_fragmentation_disabled` - Faulty device: `host_2`  The acl-skill says "When direct evidence fully matches a row in the decision table, submit. Do not chain extra probes once the match is complete."   I'm ready to submit with `link_fragmentation_disabled` as the root cause and `host_2` as the faulty device. The evidence is strong?the iptables rule blocking packets of that length, com…

---

## Case 52: `link_fragmentation_disabled` on `p4_counter` (-)

**Ground truth.** root_cause_name = `['link_fragmentation_disabled']`, faulty_devices = `['pc3']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0425043111` | 1 | _no submit() call — agent never finalised a diagnosis_ | no submission |
| **CC-Baseline** | `0426042006` | 2 | `is_anomaly=True`, `root_cause_name=['icmp_acl_block']`, `faulty_devices=['pc1']` | wrong family + wrong device |
| **SADE** | `0430152658` | 5 | `is_anomaly=True`, `root_cause_name=['link_fragmentation_disabled']`, `faulty_devices=['pc3']` | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (49 tool calls). Agent never called `submit()` — exhausted its turn budget without finalising.
- **CC-Baseline** (36 tool calls). Submitted root_cause_name=['icmp_acl_block'], faulty_devices=['pc1']; ground truth root_cause_name=['link_fragmentation_disabled'], faulty_devices=['pc3'].

**What SADE did differently**

- 35 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → ToolSearch → exec_shell → exec_shell → exec_shell → … (21 more) … → exec_shell → exec_shell → exec_shell → exec_shell → exec_shell → ToolSearch → submit).
- Decisive reasoning (last thinking before `submit`):  
  > …h rule on pc3's OUTPUT chain with `length 10:65535` DROP is exactly the `link_fragmentation_disabled` fault?it belongs to `acl-skill` despite its name. This rule prevents pc3 from sending any packets since it drops everything between 10 and 65535 bytes.  The self-ping from pc3 fails because the ICMP echo request gets dropped in the OUTPUT chain before it's even sent. For pings from pc1 or pc2 to pc3, the incoming echo requests arrive fine through the switch and are accepted by pc3's INPUT chain, but when pc3 tries to send the reply back through OUTPUT, it gets dropped?which is why those pings also fail completely.  All the symptoms now make sense: pc3 can receive traffic but can't send anyt…

---

## Case 53: `link_fragmentation_disabled` on `rip_small_internet_vpn` (l)

**Ground truth.** root_cause_name = `['link_fragmentation_disabled']`, faulty_devices = `['host_7']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0425035044` | 2 | `is_anomaly=True`, `root_cause_name=['icmp_acl_block', 'http_acl_block']`, `faulty_devices=['host_1']` | wrong family + wrong device |
| **CC-Baseline** | `0426033018` | 1 | `is_anomaly=True`, `root_cause_name=['icmp_acl_block']`, `faulty_devices=['host_4']` | wrong family + wrong device |
| **SADE** | `0427153302` | 5 | `is_anomaly=True`, `root_cause_name=['link_fragmentation_disabled']`, `faulty_devices=['host_7']` | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (27 tool calls). Submitted root_cause_name=['icmp_acl_block', 'http_acl_block'], faulty_devices=['host_1']; ground truth root_cause_name=['link_fragmentation_disabled'], faulty_devices=['host_7'].
- **CC-Baseline** (15 tool calls). Submitted root_cause_name=['icmp_acl_block'], faulty_devices=['host_4']; ground truth root_cause_name=['link_fragmentation_disabled'], faulty_devices=['host_7'].

**What SADE did differently**

- 22 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → ToolSearch → exec_shell → exec_shell → exec_shell → … (8 more) … → exec_shell → exec_shell → exec_shell → exec_shell → Skill → ToolSearch → submit).
- Decisive reasoning (last thinking before `submit`):  
  > The acl-skill confirms what I found. The iptables rule on `host_7` is: ``` Chain OUTPUT (policy ACCEPT)    10   840 DROP       0    --  *      *       0.0.0.0/0            0.0.0.0/0            length 10:65535 ```  This is clearly an iptables length-based DROP rule matching `length 10:65535`, which matches the `link_fragmentation_disabled` fingerprint in the decision table.  The faulty device is `host_7` ? it owns the matching drop rule.  Now I have direct evidence matching the decision table:   I've identified the fingerprint as an iptables length-based DROP rule on host_7, which corresponds to the `link_fragmentation_disabled` submission. Time to submit my findings.

---

## Case 54: `link_fragmentation_disabled` on `rip_small_internet_vpn` (m)

**Ground truth.** root_cause_name = `['link_fragmentation_disabled']`, faulty_devices = `['host_4']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0425034409` | 1 | `is_anomaly=True`, `root_cause_name=['icmp_acl_block']`, `faulty_devices=['host_1']` | wrong family + wrong device |
| **CC-Baseline** | `0426032607` | 2 | `is_anomaly=True`, `root_cause_name=['host_crash']`, `faulty_devices=['host_4']` | wrong fault family |
| **SADE** | `0427152841` | 5 | `is_anomaly=True`, `root_cause_name=['link_fragmentation_disabled']`, `faulty_devices=['host_4']` | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (28 tool calls). Submitted root_cause_name=['icmp_acl_block'], faulty_devices=['host_1']; ground truth root_cause_name=['link_fragmentation_disabled'], faulty_devices=['host_4'].
- **CC-Baseline** (16 tool calls). Got the device right but submitted root_cause_name=['host_crash'] (ground truth ['link_fragmentation_disabled']).

**What SADE did differently**

- 17 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → ToolSearch → exec_shell → exec_shell → Skill → … (3 more) … → exec_shell → exec_shell → exec_shell → exec_shell → Skill → ToolSearch → submit).
- Decisive reasoning (last thinking before `submit`):  
  > The acl-skill decision table confirms: - `iptables length-based DROP rule` ? `link_fragmentation_disabled`  The faulty device is `host_4` which owns the matching drop rule: ``` DROP  0  --  0.0.0.0/0  0.0.0.0/0  length 10:65535 ```  Now I have direct evidence matching the fault-family fingerprint. Let me submit.  Submit signature: `submit(is_anomaly: bool, root_cause_name: list[str], faulty_devices: list[str], confidence: float, summary: str)`   I'm ready to submit with high confidence?the iptables rule on host_4 is blocking all outbound traffic by dropping packets in the 10-65535 byte range, which directly explains the anomaly.

---

## Case 55: `link_fragmentation_disabled` on `rip_small_internet_vpn` (s)

**Ground truth.** root_cause_name = `['link_fragmentation_disabled']`, faulty_devices = `['host_1']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0425033931` | 2 | `is_anomaly=True`, `root_cause_name=['icmp_acl_block']`, `faulty_devices=['host_1']` | wrong fault family |
| **CC-Baseline** | `0426032201` | 2 | `is_anomaly=True`, `root_cause_name=['icmp_acl_block']`, `faulty_devices=['host_2']` | wrong family + wrong device |
| **SADE** | `0427152344` | 5 | `is_anomaly=True`, `root_cause_name=['link_fragmentation_disabled']`, `faulty_devices=['host_1']` | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (37 tool calls). Got the device right but submitted root_cause_name=['icmp_acl_block'] (ground truth ['link_fragmentation_disabled']).
- **CC-Baseline** (24 tool calls). Submitted root_cause_name=['icmp_acl_block'], faulty_devices=['host_2']; ground truth root_cause_name=['link_fragmentation_disabled'], faulty_devices=['host_1'].

**What SADE did differently**

- 19 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → ToolSearch → exec_shell → exec_shell → exec_shell → … (5 more) … → exec_shell → exec_shell → exec_shell → exec_shell → Skill → ToolSearch → submit).
- Decisive reasoning (last thinking before `submit`):  
  > I have all the evidence I need. Let me submit now.  - `is_anomaly`: true - `root_cause_name`: ["link_fragmentation_disabled"] - `faulty_devices`: ["host_1"]  The evidence: - host_1 has an iptables OUTPUT chain rule: `DROP all -- * * 0.0.0.0/0 0.0.0.0/0 length 10:65535` - This blocks all outgoing IP packets ? 10 bytes on host_1 - This explains why host_1 can't reach its gateway, host_2, or the web servers   - ARP still works since it operates at layer 2 and bypasses the iptables filtering, which I confirmed with the arping test

---

## Case 56: `link_fragmentation_disabled` on `simple_bgp` (-)

**Ground truth.** root_cause_name = `['link_fragmentation_disabled']`, faulty_devices = `['pc2']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0425044406` | 2 | `is_anomaly=True`, `root_cause_name=['icmp_acl_block']`, `faulty_devices=['pc1']` | wrong family + wrong device |
| **CC-Baseline** | `0426043036` | 2 | `is_anomaly=True`, `root_cause_name=['icmp_acl_block']`, `faulty_devices=['pc1']` | wrong family + wrong device |
| **SADE** | `0427170240` | 5 | `is_anomaly=True`, `root_cause_name=['link_fragmentation_disabled']`, `faulty_devices=['pc2']` | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (30 tool calls). Submitted root_cause_name=['icmp_acl_block'], faulty_devices=['pc1']; ground truth root_cause_name=['link_fragmentation_disabled'], faulty_devices=['pc2'].
- **CC-Baseline** (35 tool calls). Submitted root_cause_name=['icmp_acl_block'], faulty_devices=['pc1']; ground truth root_cause_name=['link_fragmentation_disabled'], faulty_devices=['pc2'].

**What SADE did differently**

- 32 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → ToolSearch → exec_shell → exec_shell → Skill → … (18 more) … → exec_shell → exec_shell → exec_shell → exec_shell → Skill → ToolSearch → submit).
- Decisive reasoning (last thinking before `submit`):  
  > The acl-skill confirms my finding. The decision table clearly matches:  | iptables length-based DROP rule | `link_fragmentation_disabled` |  The fingerprint in pc2's iptables OUTPUT chain: `14  1176 DROP  0  --  *  *  0.0.0.0/0  0.0.0.0/0  length 10:65535`  This is an iptables length-based DROP rule ? `link_fragmentation_disabled`.  Faulty device: `pc2` Root cause: `link_fragmentation_disabled`   I'm ready to submit my findings.

---

## Case 57: `mac_address_conflict` on `dc_clos_bgp` (m)

**Ground truth.** root_cause_name = `['mac_address_conflict']`, faulty_devices = `['spine_router_1_3', 'leaf_router_1_3']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0425115218` | 1 | `is_anomaly=True`, `root_cause_name=['bgp_blackhole_route_leak']`, `faulty_devices=['leaf_router_0_0', 'leaf_router_0_1', 'spine_router_0_0', 'spine_router_0_1']` | wrong family + wrong device |
| **CC-Baseline** | `0426154443` | 1 | _no submit() call — agent never finalised a diagnosis_ | no submission |
| **SADE** | `0429050429` | 5 | `is_anomaly=True`, `root_cause_name=['mac_address_conflict']`, `faulty_devices=['leaf_router_1_3', 'spine_router_1_3']` | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (11 tool calls). Submitted root_cause_name=['bgp_blackhole_route_leak'], faulty_devices=['leaf_router_0_0', 'leaf_router_0_1', 'spine_router_0_0', 'spine_router_0_1']; ground truth root_cause_name=['mac_address_conflict'], faulty_devices=['leaf_router_1_3', 'spine_router_1_3'].
- **CC-Baseline** (52 tool calls). Agent never called `submit()` — exhausted its turn budget without finalising.

**What SADE did differently**

- 12 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → Skill → Bash → Bash → Skill → ToolSearch → exec_shell → exec_shell → ToolSearch → submit).
- Decisive reasoning (last thinking before `submit`):  
  > Direct confirmation:  - `leaf_router_1_3`: **eth3** has MAC `ee:89:8a:0a:f2:16` - `spine_router_1_3`: **eth0** has MAC `ee:89:8a:0a:f2:16`  Both routers have the exact same MAC address `ee:89:8a:0a:f2:16` on their interfaces. This is a confirmed `mac_address_conflict`.  Now let me check which interfaces are connected:   - `spine_router_1_3:eth2` connects to `leaf_router_1_0:eth3`, and `eth3` connects to `leaf_router_1_1:eth3`. Let me verify the exact topology to see where the conflicting interfaces actually link up.  Looking at the connections, `leaf_router_1_3:eth3` should connect to `spine_router_1_3:eth5` based on the topology. Now I'm noticing that both `leaf_router_1_3:eth3` and `spine_…

---

## Case 58: `mac_address_conflict` on `dc_clos_bgp` (s)

**Ground truth.** root_cause_name = `['mac_address_conflict']`, faulty_devices = `['super_spine_router_0', 'spine_router_0_0']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0425114949` | 1 | _submitted empty diagnosis_ | empty submission |
| **CC-Baseline** | `0426153901` | 1 | _submitted empty diagnosis_ | empty submission |
| **SADE** | `0429050127` | 5 | `is_anomaly=True`, `root_cause_name=['mac_address_conflict']`, `faulty_devices=['spine_router_0_0', 'super_spine_router_0']` | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (14 tool calls). Submitted with empty root_cause_name / faulty_devices.
- **CC-Baseline** (28 tool calls). Submitted with empty root_cause_name / faulty_devices.

**What SADE did differently**

- 12 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → Skill → Bash → Bash → Skill → ToolSearch → exec_shell → exec_shell → ToolSearch → submit).
- Decisive reasoning (last thinking before `submit`):  
  > Direct confirmation: - `spine_router_0_0` **eth0** has MAC `0e:53:53:2b:88:94` - `super_spine_router_0` **eth0** has MAC `0e:53:53:2b:88:94`  Both devices have the same MAC `0e:53:53:2b:88:94` on their `eth0` interfaces, which are directly connected to each other: - `super_spine_router_0:eth0 ? spine_router_0_0:eth0`   This is a confirmed MAC address conflict ? both routers are using the identical MAC on the interfaces connecting them directly to each other.  The evidence is solid: the l2_snapshot data shows the duplicate MAC `0e:53:53:2b:88:94` on both devices, and the direct `ip link show` output confirms it. The decision table is clear ? when two different devices share the same `link/eth…

---

## Case 59: `mac_address_conflict` on `dc_clos_service` (s)

**Ground truth.** root_cause_name = `['mac_address_conflict']`, faulty_devices = `['super_spine_router_0', 'spine_router_0_1']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0425120100` | 1 | _submitted empty diagnosis_ | empty submission |
| **CC-Baseline** | `0426161530` | 1 | _no submit() call — agent never finalised a diagnosis_ | no submission |
| **SADE** | `0429051723` | 5 | `is_anomaly=True`, `root_cause_name=['mac_address_conflict']`, `faulty_devices=['spine_router_0_1', 'super_spine_router_0']` | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (20 tool calls). Submitted with empty root_cause_name / faulty_devices.
- **CC-Baseline** (51 tool calls). Agent never called `submit()` — exhausted its turn budget without finalising.

**What SADE did differently**

- 13 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → Skill → Bash → Bash → Skill → Skill → ToolSearch → exec_shell → exec_shell → ToolSearch → submit).
- Decisive reasoning (last thinking before `submit`):  
  > …outer_0:eth0` connects to `spine_router_0_0:eth0`   - `super_spine_router_0:eth1` connects to `spine_router_0_1:eth0` (which has MAC `3e:94:bb:24:c7:6e`)  The conflict is clear: `spine_router_0_1:eth0` and `super_spine_router_0:eth0` both claim the same MAC address `fa:64:04:a1:3a:68`, even though they're connected through different interfaces on the super spine router.  Let me trace this more carefully?`super_spine_router_0:eth0` goes to `spine_router_0_0`, while `eth1` goes to `spine_router_0_1`, so the duplicate MAC isn't on directly connected interfaces. I'm seeing the rest of the network connections now?super_spine's eth1 links to spine_0_1, and eth2 connects to the client. But there's…

---

## Case 60: `mac_address_conflict` on `ospf_enterprise_static` (l)

**Ground truth.** root_cause_name = `['mac_address_conflict']`, faulty_devices = `['switch_access_1_2_3', 'host_1_2_3_2']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0425122552` | 1 | `is_anomaly=True`, `root_cause_name=['ospf_area_misconfiguration']`, `faulty_devices=['router_core_1', 'router_core_2', 'router_core_3', 'switch_dist_1_1', 'switch_dist_2_1', 'switch_server_access']` | wrong family + wrong device |
| **CC-Baseline** | `0426164602` | 1 | _no submit() call — agent never finalised a diagnosis_ | no submission |
| **SADE** | `0429054513` | 5 | `is_anomaly=True`, `root_cause_name=['mac_address_conflict']`, `faulty_devices=['switch_access_1_2_3', 'host_1_2_3_2']` | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (30 tool calls). Submitted root_cause_name=['ospf_area_misconfiguration'], faulty_devices=['router_core_1', 'router_core_2', 'router_core_3', 'switch_dist_1_1', 'switch_dist_2_1', 'switch_server_access']; ground truth root_cause_name=['mac_address_conflict'], faulty_devices=['host_1_2_3_2', 'switch_access_1_2_3'].
- **CC-Baseline** (64 tool calls). Agent never called `submit()` — exhausted its turn budget without finalising.

**What SADE did differently**

- 19 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → Skill → Bash → ToolSearch → exec_shell → … (5 more) … → exec_shell → exec_shell → exec_shell → exec_shell → Skill → ToolSearch → submit).
- Decisive reasoning (last thinking before `submit`):  
  > The `mac-address-conflict-skill` confirms: - Two different devices show the exact same `link/ether` MAC: `22:95:9b:82:85:44`   - `switch_access_1_2_3`: `br0`/`eth0` = `22:95:9b:82:85:44`   - `host_1_2_3_2`: `eth0` = `22:95:9b:82:85:44`  The decision table fingerprint matches: "Two different devices share the same `link/ether` value ? `mac_address_conflict`"   I've confirmed the match is complete and `mac_address_conflict` is available in the problem list, so I'm submitting now with the faulty devices `switch_access_1_2_3` and `host_1_2_3_2`.

---

## Case 61: `mac_address_conflict` on `ospf_enterprise_static` (m)

**Ground truth.** root_cause_name = `['mac_address_conflict']`, faulty_devices = `['web_server_3', 'switch_server_access']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0425122034` | 1 | _submitted empty diagnosis_ | empty submission |
| **CC-Baseline** | `0426163738` | 1 | _no submit() call — agent never finalised a diagnosis_ | no submission |
| **SADE** | `0429053926` | 5 | `is_anomaly=True`, `root_cause_name=['mac_address_conflict']`, `faulty_devices=['switch_server_access', 'web_server_3']` | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (27 tool calls). Submitted with empty root_cause_name / faulty_devices.
- **CC-Baseline** (52 tool calls). Agent never called `submit()` — exhausted its turn budget without finalising.

**What SADE did differently**

- 25 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → ToolSearch → exec_shell → exec_shell → exec_shell → … (11 more) … → exec_shell → Skill → Bash → Bash → Skill → ToolSearch → submit).
- Decisive reasoning (last thinking before `submit`):  
  > I have direct evidence from `l2_snapshot` that `switch_server_access` and `web_server_3` share the same MAC address `46:3f:6b:d0:fb:0b`. This matches the decision table row: "Two different devices share the same `link/ether` value" ? `mac_address_conflict`.  Per the skill instructions: "When direct evidence fully matches a row in the decision table, submit. Do not chain extra probes once the match is complete."  Let me confirm the faulty devices with one quick `ip link show` to verify the MAC on both devices, then submit.   Actually, the l2_snapshot already provided direct `link/ether` comparison showing both devices have MAC `46:3f:6b:d0:fb:0b`. This IS direct evidence. I should submit now …

---

## Case 62: `mac_address_conflict` on `ospf_enterprise_static` (s)

**Ground truth.** root_cause_name = `['mac_address_conflict']`, faulty_devices = `['router_core_3', 'switch_server_access']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0425121245` | 1 | `is_anomaly=True`, `root_cause_name=['ospf_neighbor_missing']`, `faulty_devices=['router_core_1', 'router_core_2', 'router_core_3', 'switch_dist_1_1', 'switch_dist_2_1', 'switch_server_access']` | wrong fault family |
| **CC-Baseline** | `0426163302` | 1 | _no submit() call — agent never finalised a diagnosis_ | no submission |
| **SADE** | `0429053357` | 5 | `is_anomaly=True`, `root_cause_name=['mac_address_conflict']`, `faulty_devices=['router_core_3', 'switch_server_access']` | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (61 tool calls). Got the device right but submitted root_cause_name=['ospf_neighbor_missing'] (ground truth ['mac_address_conflict']).
- **CC-Baseline** (51 tool calls). Agent never called `submit()` — exhausted its turn budget without finalising.

**What SADE did differently**

- 24 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → ToolSearch → exec_shell → exec_shell → exec_shell → … (10 more) … → Bash → Bash → Skill → exec_shell → exec_shell → ToolSearch → submit).
- Decisive reasoning (last thinking before `submit`):  
  > Perfect. The direct `ip link show` confirms the duplicate MAC:  - **router_core_3** ? `eth0` has `link/ether ce:6e:6c:87:d0:6b` - **switch_server_access** ? `eth5` has `link/ether ce:6e:6c:87:d0:6b`  Both devices share the EXACT same MAC address `ce:6e:6c:87:d0:6b` on their respective interfaces: - `router_core_3:eth0` ? this is the interface connected to `router_core_2:eth0` (per topology: `router_core_1:eth0, router_core_2:eth0`)... wait, let me check the topology again.   - Actually, looking at the full topology, `router_core_3:eth0` connects to `router_core_1:eth1`, and `router_core_3:eth2` connects to `switch_server_access:eth5`. So the duplicate MAC is on `router_core_3:eth0` (which ta…

---

## Case 63: `mac_address_conflict` on `p4_mpls` (-)

**Ground truth.** root_cause_name = `['mac_address_conflict']`, faulty_devices = `['switch_1', 'switch_3']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0425133252` | 1 | _no submit() call — agent never finalised a diagnosis_ | no submission |
| **CC-Baseline** | `0426181110` | 1 | _no submit() call — agent never finalised a diagnosis_ | no submission |
| **SADE** | `0430165917` | 5 | `is_anomaly=True`, `root_cause_name=['mac_address_conflict']`, `faulty_devices=['switch_1', 'switch_3']` | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (41 tool calls). Agent never called `submit()` — exhausted its turn budget without finalising.
- **CC-Baseline** (84 tool calls). Agent never called `submit()` — exhausted its turn budget without finalising.

**What SADE did differently**

- 13 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → Skill → Bash → Bash → Skill → Skill → ToolSearch → exec_shell → exec_shell → ToolSearch → submit).
- Decisive reasoning (last thinking before `submit`):  
  > Now I'll submit with the confirmed findings: - is_anomaly: true - root_cause_name: ["mac_address_conflict"] - faulty_devices: ["switch_1", "switch_3"] - confidence: 0.95 (high confidence, direct MAC comparison confirmed)  Wait, the submit tool doesn't have a `confidence` or `summary` parameter based on the schema above. Let me check what parameters it accepts: `is_anomaly`, `faulty_devices`, `root_cause_name`. Those are the three required ones. No `confidence` or `summary` in this version of the tool.  Let me submit.

---

## Case 64: `mac_address_conflict` on `rip_small_internet_vpn` (l)

**Ground truth.** root_cause_name = `['mac_address_conflict']`, faulty_devices = `['external_router_1', 'web_server_1_6']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0425124121` | 1 | _submitted empty diagnosis_ | empty submission |
| **CC-Baseline** | `0426171646` | 1 | _no submit() call — agent never finalised a diagnosis_ | no submission |
| **SADE** | `0429055735` | 5 | `is_anomaly=True`, `root_cause_name=['mac_address_conflict']`, `faulty_devices=['external_router_1', 'web_server_1_6']` | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (31 tool calls). Submitted with empty root_cause_name / faulty_devices.
- **CC-Baseline** (45 tool calls). Agent never called `submit()` — exhausted its turn budget without finalising.

**What SADE did differently**

- 12 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → Skill → Bash → Bash → Skill → ToolSearch → exec_shell → exec_shell → ToolSearch → submit).
- Decisive reasoning (last thinking before `submit`):  
  > This directly confirms the duplicate MAC:  - `external_router_1` eth0: `link/ether a6:da:f4:d5:76:84` - `web_server_1_6` eth0: `link/ether a6:da:f4:d5:76:84`  Both devices have the **same MAC address** `a6:da:f4:d5:76:84` on their `eth0` interfaces. This is the canonical `mac_address_conflict` signal ? two different devices share the same `link/ether` value on interfaces that are on the same Layer 2 segment (the 20.0.0.x/24 LAN bridged behind `external_router_1`).   The duplicate MAC will cause ARP instability on the 20.0.0.x/24 segment since both `external_router_1` and `web_server_1_6` are claiming the same hardware address. According to the decision criteria, this is a clear `mac_address_…

---

## Case 65: `mac_address_conflict` on `rip_small_internet_vpn` (m)

**Ground truth.** root_cause_name = `['mac_address_conflict']`, faulty_devices = `['external_router_1', 'vpn_server_1']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0425123539` | 1 | `is_anomaly=True`, `root_cause_name=['host_vpn_membership_missing']`, `faulty_devices=['host_2']` | wrong family + wrong device |
| **CC-Baseline** | `0426170442` | 1 | `is_anomaly=True`, `root_cause_name=['host_vpn_membership_missing']`, `faulty_devices=['host_1']` | wrong family + wrong device |
| **SADE** | `0429055459` | 5 | `is_anomaly=True`, `root_cause_name=['mac_address_conflict']`, `faulty_devices=['external_router_1', 'vpn_server_1']` | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (24 tool calls). Submitted root_cause_name=['host_vpn_membership_missing'], faulty_devices=['host_2']; ground truth root_cause_name=['mac_address_conflict'], faulty_devices=['vpn_server_1', 'external_router_1'].
- **CC-Baseline** (40 tool calls). Submitted root_cause_name=['host_vpn_membership_missing'], faulty_devices=['host_1']; ground truth root_cause_name=['mac_address_conflict'], faulty_devices=['vpn_server_1', 'external_router_1'].

**What SADE did differently**

- 12 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → Skill → Bash → Bash → Skill → ToolSearch → exec_shell → exec_shell → ToolSearch → submit).
- Decisive reasoning (last thinking before `submit`):  
  > …ion table.  The faulty devices are `external_router_1` and `vpn_server_1`, and I've confirmed `mac_address_conflict` is available in the problem list, so I'm ready to move forward with submission.  I'm realizing the MAC conflict is more subtle than I initially thought ? both devices share the same MAC address `f2:36:6e:5b:69:09` but are on different network segments, which still constitutes a conflict since L2 identity should be unique across the infrastructure. actual conflicting interface on `external_router_1` is `eth0`, and on `vpn_server_1` is `eth0`.  `external_router_1:eth0` connects to `gateway_router:eth2` - this is the WAN link. `vpn_server_1:eth0` connects to `external_router_1:e…

---

## Case 66: `mac_address_conflict` on `rip_small_internet_vpn` (s)

**Ground truth.** root_cause_name = `['mac_address_conflict']`, faulty_devices = `['router1', 'gateway_router']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0425122945` | 1 | _submitted empty diagnosis_ | empty submission |
| **CC-Baseline** | `0426165512` | 1 | `is_anomaly=True`, `root_cause_name=['host_vpn_membership_missing']`, `faulty_devices=['host_1']` | wrong family + wrong device |
| **SADE** | `0429055219` | 5 | `is_anomaly=True`, `root_cause_name=['mac_address_conflict']`, `faulty_devices=['gateway_router', 'router1']` | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (31 tool calls). Submitted with empty root_cause_name / faulty_devices.
- **CC-Baseline** (38 tool calls). Submitted root_cause_name=['host_vpn_membership_missing'], faulty_devices=['host_1']; ground truth root_cause_name=['mac_address_conflict'], faulty_devices=['router1', 'gateway_router'].

**What SADE did differently**

- 10 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → Skill → Bash → Bash → Skill → Skill → ToolSearch → submit).
- Decisive reasoning (last thinking before `submit`):  
  > Now let me submit the result.

---

## Case 67: `mac_address_conflict` on `sdn_clos` (s)

**Ground truth.** root_cause_name = `['mac_address_conflict']`, faulty_devices = `['spine_1', 'leaf_2']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0425130151` | 1 | `is_anomaly=True`, `root_cause_name=['link_detach']`, `faulty_devices=['spine_1', 'leaf_1']` | wrong fault family |
| **CC-Baseline** | `0426173130` | 1 | `is_anomaly=True`, `root_cause_name=['link_detach']`, `faulty_devices=['leaf_1', 'spine_1']` | wrong fault family |
| **SADE** | `0430160806` | 5 | `is_anomaly=True`, `root_cause_name=['mac_address_conflict']`, `faulty_devices=['leaf_2', 'spine_1']` | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (11 tool calls). Got the device right but submitted root_cause_name=['link_detach'] (ground truth ['mac_address_conflict']).
- **CC-Baseline** (23 tool calls). Got the device right but submitted root_cause_name=['link_detach'] (ground truth ['mac_address_conflict']).

**What SADE did differently**

- 8 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → Skill → Bash → Bash → Skill → submit).
- Decisive reasoning (last thinking before `submit`):  
  > The `mac-address-conflict-skill` confirms that the canonical fault is `mac_address_conflict`. The `l2_snapshot` already provided direct evidence:  - MAC `1e:37:43:52:45:c1` is shared between `leaf_2` and `spine_1`  This matches the decision table fingerprint: "Two different devices share the same `link/ether` value" ? `mac_address_conflict`  The evidence is already conclusive. Per the skill: "When direct evidence fully matches a row in the decision table, submit. Do not chain extra probes once the match is complete."  Let me proceed to Phase 5 ? submission.   I've identified the faulty devices as `leaf_2` and `spine_1` with `mac_address_conflict` as the root cause, so I'm ready to submit the…

---

## Case 68: `mac_address_conflict` on `sdn_star` (l)

**Ground truth.** root_cause_name = `['mac_address_conflict']`, faulty_devices = `['switch_10', 'host_10']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0425125731` | 1 | _no submit() call — agent never finalised a diagnosis_ | no submission |
| **CC-Baseline** | `0426172825` | 1 | `is_anomaly=True`, `root_cause_name=['link_detach']`, `faulty_devices=['switch_0', 'switch_1']` | wrong family + wrong device |
| **SADE** | `0430160433` | 5 | `is_anomaly=True`, `root_cause_name=['mac_address_conflict']`, `faulty_devices=['host_10', 'switch_10']` | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (25 tool calls). Agent never called `submit()` — exhausted its turn budget without finalising.
- **CC-Baseline** (18 tool calls). Submitted root_cause_name=['link_detach'], faulty_devices=['switch_0', 'switch_1']; ground truth root_cause_name=['mac_address_conflict'], faulty_devices=['host_10', 'switch_10'].

**What SADE did differently**

- 10 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → Skill → Bash → Bash → Skill → Skill → ToolSearch → submit).
- Decisive reasoning (last thinking before `submit`):  
  > Now I'll submit the findings. The root_cause_name is `mac_address_conflict`, faulty_devices are `host_10` and `switch_10`.

---

## Case 69: `mac_address_conflict` on `sdn_star` (m)

**Ground truth.** root_cause_name = `['mac_address_conflict']`, faulty_devices = `['switch_4', 'host_4']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0425125133` | 1 | `is_anomaly=True`, `root_cause_name=['link_detach']`, `faulty_devices=['switch_0:eth4', 'switch_1:eth2']` | wrong family + wrong device |
| **CC-Baseline** | `0426172523` | 1 | `is_anomaly=True`, `root_cause_name=['link_detach']`, `faulty_devices=['switch_0', 'switch_1']` | wrong family + wrong device |
| **SADE** | `0430160139` | 5 | `is_anomaly=True`, `root_cause_name=['mac_address_conflict']`, `faulty_devices=['host_4', 'switch_4']` | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (24 tool calls). Submitted root_cause_name=['link_detach'], faulty_devices=['switch_0:eth4', 'switch_1:eth2']; ground truth root_cause_name=['mac_address_conflict'], faulty_devices=['host_4', 'switch_4'].
- **CC-Baseline** (23 tool calls). Submitted root_cause_name=['link_detach'], faulty_devices=['switch_0', 'switch_1']; ground truth root_cause_name=['mac_address_conflict'], faulty_devices=['host_4', 'switch_4'].

**What SADE did differently**

- 12 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → Skill → Bash → Bash → Skill → Skill → ToolSearch → exec_shell → exec_shell → submit).
- Decisive reasoning (last thinking before `submit`):  
  > …8f:60` **switch_4**: `eth0: link/ether 76:5d:8b:3c:8f:60` (this is switch_4's eth0, which is connected to host_4, so they share the same MAC)  Wait, I see something interesting here. On `switch_4`, the internal bridge interfaces (`switch_4` and `ovs-system`) have different MACs:   - `ovs-system`: `ea:0c:0a:1b:07:1d` - `switch_4` (bridge): `92:68:38:fa:f6:41` - `eth0`: `76:5d:8b:3c:8f:60` ? same as host_4's eth0!  So the duplicate MAC is between host_4's eth0 and switch_4's eth0, which makes sense since they're directly connected to each other.  The problem is that both endpoints of this link claim the same MAC address ? when ARP requests come in for host_4's IP, both host_4 and switch_4's e…

---

## Case 70: `mac_address_conflict` on `sdn_star` (s)

**Ground truth.** root_cause_name = `['mac_address_conflict']`, faulty_devices = `['switch_0', 'switch_4']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0425124752` | 1 | _submitted empty diagnosis_ | empty submission |
| **CC-Baseline** | `0426172325` | 1 | `is_anomaly=True`, `root_cause_name=['link_detach']`, `faulty_devices=['switch_0', 'switch_1']` | wrong fault family |
| **SADE** | `0430155925` | 5 | `is_anomaly=True`, `root_cause_name=['mac_address_conflict']`, `faulty_devices=['switch_0', 'switch_4']` | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (41 tool calls). Submitted with empty root_cause_name / faulty_devices.
- **CC-Baseline** (13 tool calls). Got the device right but submitted root_cause_name=['link_detach'] (ground truth ['mac_address_conflict']).

**What SADE did differently**

- 9 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → Skill → Bash → Bash → Skill → ToolSearch → submit).
- Decisive reasoning (last thinking before `submit`):  
  > The mac-address-conflict-skill confirms the duplicate MAC. The l2_snapshot already showed:  **Duplicate MAC: `d2:cd:61:5b:43:d4` shared by `switch_0` and `switch_4`**  This matches the decision table: "Two different devices share the same `link/ether` value ? `mac_address_conflict`"  The evidence is direct from `l2_snapshot`, which is the canonical MAC inventory helper. Per the skill's decision table, this is a direct match for `mac_address_conflict`.  Let me confirm this with a direct `ip link show` on switch_0 and switch_4 to cement the evidence before submitting.   Actually, I'm overcomplicating this?the skill's own guidance says to submit once direct evidence fully matches a decision tab…

---

## Case 71: `mac_address_conflict` on `simple_bgp` (-)

**Ground truth.** root_cause_name = `['mac_address_conflict']`, faulty_devices = `['router2', 'pc2']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0425133847` | 1 | _submitted empty diagnosis_ | empty submission |
| **CC-Baseline** | `0426181734` | 1 | _submitted empty diagnosis_ | empty submission |
| **SADE** | `0429072220` | 5 | `is_anomaly=True`, `root_cause_name=['mac_address_conflict']`, `faulty_devices=['pc2', 'router2']` | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (12 tool calls). Submitted with empty root_cause_name / faulty_devices.
- **CC-Baseline** (20 tool calls). Submitted with empty root_cause_name / faulty_devices.

**What SADE did differently**

- 11 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → Skill → Bash → Bash → Skill → ToolSearch → exec_shell → exec_shell → submit).
- Decisive reasoning (last thinking before `submit`):  
  > The duplicate MAC is confirmed: - `pc2` eth0: `aa:46:05:d2:e6:c3` - `router2` eth0: `aa:46:05:d2:e6:c3`  Both devices share the exact same MAC address `aa:46:05:d2:e6:c3` on their respective `eth0` interfaces.   The `router2` has: - eth0: `aa:46:05:d2:e6:c3` (connects to router1)   - eth1: `2e:0b:c6:6e:c8:7e` (connects to pc2)  And `pc2` has: - eth0: `aa:46:05:d2:e6:c3` (connects to router2's eth1 segment)  So the inter-router link connects `router1:eth0` to `router2:eth0`, while the router-to-pc2 link connects `router2:eth1` to `pc2:eth0` ? yet both `router2:eth0` and `pc2:eth0` are using the same MAC address, which is the core problem here.  Even though they're on different network segment…

---

## Case 72: `ospf_acl_block` on `ospf_enterprise_static` (l)

**Ground truth.** root_cause_name = `['ospf_acl_block']`, faulty_devices = `['switch_dist_2_2']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0425090701` | 1 | _submitted empty diagnosis_ | empty submission |
| **CC-Baseline** | `0426133653` | 1 | _no submit() call — agent never finalised a diagnosis_ | no submission |
| **SADE** | `0429093059` | 5 | `is_anomaly=True`, `root_cause_name=['ospf_acl_block']`, `faulty_devices=['switch_dist_2_2']` | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (40 tool calls). Submitted with empty root_cause_name / faulty_devices.
- **CC-Baseline** (42 tool calls). Agent never called `submit()` — exhausted its turn budget without finalising.

**What SADE did differently**

- 17 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → ToolSearch → Skill → Bash → ToolSearch → … (3 more) … → exec_shell → Skill → Bash → exec_shell → exec_shell → ToolSearch → submit).
- Decisive reasoning (last thinking before `submit`):  
  > Confirmed! The `switch_dist_2_2` has an nft firewall that drops ALL OSPF traffic (protocol ospf = IP protocol 89):  ``` table inet filter {     chain input {         type filter hook input priority filter; policy accept;         ip protocol ospf drop         ip protocol ospf drop     }      chain forward {         type filter hook forward priority filter; policy accept;   ```  Blocking OSPF on all chains...  So the culprit is `switch_dist_2_2` with its nft rules dropping OSPF traffic across input, forward, and output chains, while `router_core_2` has no such restrictions. This matches the `ospf_acl_block` fault pattern.  I'm verifying that `ospf_acl_block` is in the available problems list?i…

---

## Case 73: `ospf_acl_block` on `ospf_enterprise_static` (s)

**Ground truth.** root_cause_name = `['ospf_acl_block']`, faulty_devices = `['switch_server_access']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0425085638` | 1 | `is_anomaly=True`, `root_cause_name=['ospf_neighbor_missing']`, `faulty_devices=['switch_dist_1_1', 'switch_dist_2_1']` | wrong family + wrong device |
| **CC-Baseline** | `0426132356` | 1 | _no submit() call — agent never finalised a diagnosis_ | no submission |
| **SADE** | `0429091903` | 5 | `is_anomaly=True`, `root_cause_name=['ospf_acl_block']`, `faulty_devices=['switch_server_access']` | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (39 tool calls). Submitted root_cause_name=['ospf_neighbor_missing'], faulty_devices=['switch_dist_1_1', 'switch_dist_2_1']; ground truth root_cause_name=['ospf_acl_block'], faulty_devices=['switch_server_access'].
- **CC-Baseline** (52 tool calls). Agent never called `submit()` — exhausted its turn budget without finalising.

**What SADE did differently**

- 18 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → ToolSearch → exec_shell → exec_shell → exec_shell → … (4 more) … → exec_shell → exec_shell → exec_shell → exec_shell → Skill → ToolSearch → submit).
- Decisive reasoning (last thinking before `submit`):  
  > The decision table confirms: `nft` drops OSPF traffic (protocol 89) ? `ospf_acl_block` ? faulty device: `switch_server_access`.  Now let me submit.

---

## Case 74: `southbound_port_block` on `sdn_clos` (s)

**Ground truth.** root_cause_name = `['southbound_port_block']`, faulty_devices = `['controller']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0425155448` | 1 | _submitted empty diagnosis_ | empty submission |
| **CC-Baseline** | `0427004217` | 1 | _no submit() call — agent never finalised a diagnosis_ | no submission |
| **SADE** | `0429142929` | 5 | `is_anomaly=True`, `root_cause_name=['southbound_port_block']`, `faulty_devices=['controller']` | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (17 tool calls). Submitted with empty root_cause_name / faulty_devices.
- **CC-Baseline** (40 tool calls). Agent never called `submit()` — exhausted its turn budget without finalising.

**What SADE did differently**

- 21 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → ToolSearch → exec_shell → exec_shell → exec_shell → … (7 more) … → exec_shell → exec_shell → exec_shell → exec_shell → exec_shell → ToolSearch → submit).
- Decisive reasoning (last thinking before `submit`):  
  > Found it! The controller has nftables rules that **DROP all TCP traffic to port 6633** in all chains (input, forward, output):  ``` table inet filter {     chain input {         type filter hook input priority filter; policy accept;         tcp dport 6633 drop     }      chain forward {         type filter hook forward priority filter; policy accept;         tcp dport 6633 drop     }      chain output {         type filter hook output priority filter; policy accept;         tcp dport 6633 drop     } } ```  This is the root cause! Port 6633 (the OpenFlow southbound port) is blocked by nftables on the controller itself.   This matches the `southbound_port_block` fault. The nftables rules preve…

---

## Case 75: `southbound_port_block` on `sdn_star` (l)

**Ground truth.** root_cause_name = `['southbound_port_block']`, faulty_devices = `['controller']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0425155055` | 1 | _submitted empty diagnosis_ | empty submission |
| **CC-Baseline** | `0427003843` | 1 | _no submit() call — agent never finalised a diagnosis_ | no submission |
| **SADE** | `0429142558` | 5 | `is_anomaly=True`, `root_cause_name=['southbound_port_block']`, `faulty_devices=['controller']` | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (23 tool calls). Submitted with empty root_cause_name / faulty_devices.
- **CC-Baseline** (39 tool calls). Agent never called `submit()` — exhausted its turn budget without finalising.

**What SADE did differently**

- 26 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → ToolSearch → exec_shell → exec_shell → exec_shell → … (12 more) … → exec_shell → exec_shell → exec_shell → exec_shell → exec_shell → ToolSearch → submit).
- Decisive reasoning (last thinking before `submit`):  
  > The evidence is clear. Let me submit with the confirmed root cause.  - `is_anomaly`: true - `root_cause_name`: ["southbound_port_block"] - `faulty_devices`: ["controller"] - `confidence`: 0.99

---

## Case 76: `southbound_port_block` on `sdn_star` (m)

**Ground truth.** root_cause_name = `['southbound_port_block']`, faulty_devices = `['controller']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0425154712` | 1 | `is_anomaly=True`, `root_cause_name=['link_detach']`, `faulty_devices=['switch_1']` | wrong family + wrong device |
| **CC-Baseline** | `0427003441` | 1 | _no submit() call — agent never finalised a diagnosis_ | no submission |
| **SADE** | `0429142210` | 5 | `is_anomaly=True`, `root_cause_name=['southbound_port_block']`, `faulty_devices=['controller']` | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (31 tool calls). Submitted root_cause_name=['link_detach'], faulty_devices=['switch_1']; ground truth root_cause_name=['southbound_port_block'], faulty_devices=['controller'].
- **CC-Baseline** (39 tool calls). Agent never called `submit()` — exhausted its turn budget without finalising.

**What SADE did differently**

- 30 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → ToolSearch → exec_shell → exec_shell → exec_shell → … (16 more) … → exec_shell → exec_shell → exec_shell → exec_shell → Skill → ToolSearch → submit).
- Decisive reasoning (last thinking before `submit`):  
  > The ACL skill's decision table doesn't have a specific row for TCP port 6633 (OpenFlow/SDN southbound). However, based on the fingerprint we found ? a TCP port 6633 DROP rule on the controller ? this matches the `southbound_port_block` fault type from the list of available problems.  The ACL skill covers standard ACL blocks. The `southbound_port_block` is a specific SDN fault that involves blocking TCP port 6633. This isn't directly in the ACL skill's decision table, but it's the closest match to what we see. The available problems list includes `southbound_port_block` as a distinct fault type.   I'll set the root cause to `southbound_port_block` with the controller as the faulty device and …

---

## Case 77: `southbound_port_block` on `sdn_star` (s)

**Ground truth.** root_cause_name = `['southbound_port_block']`, faulty_devices = `['controller']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0425154253` | 1 | _submitted empty diagnosis_ | empty submission |
| **CC-Baseline** | `0427002730` | 1 | _no submit() call — agent never finalised a diagnosis_ | no submission |
| **SADE** | `0429141911` | 5 | `is_anomaly=True`, `root_cause_name=['southbound_port_block']`, `faulty_devices=['controller']` | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (26 tool calls). Submitted with empty root_cause_name / faulty_devices.
- **CC-Baseline** (43 tool calls). Agent never called `submit()` — exhausted its turn budget without finalising.

**What SADE did differently**

- 22 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → ToolSearch → exec_shell → exec_shell → exec_shell → … (8 more) … → exec_shell → get_host_net_config → exec_shell → exec_shell → exec_shell → ToolSearch → submit).
- Decisive reasoning (last thinking before `submit`):  
  > Let me submit now with the confirmed findings.

---

## Case 78: `web_dos_attack` on `ospf_enterprise_static` (l)

**Ground truth.** root_cause_name = `['web_dos_attack']`, faulty_devices = `['web_server_0']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0425220529` | 1 | `is_anomaly=True`, `root_cause_name=['flow_rule_loop']`, `faulty_devices=['switch_access_2_1_1']` | wrong family + wrong device |
| **CC-Baseline** | `0427055555` | 1 | _no submit() call — agent never finalised a diagnosis_ | no submission |
| **SADE** | `0429190244` | 5 | `is_anomaly=True`, `root_cause_name=['web_dos_attack']`, `faulty_devices=['web_server_0']` | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (30 tool calls). Submitted root_cause_name=['flow_rule_loop'], faulty_devices=['switch_access_2_1_1']; ground truth root_cause_name=['web_dos_attack'], faulty_devices=['web_server_0'].
- **CC-Baseline** (27 tool calls). Agent never called `submit()` — exhausted its turn budget without finalising.

**What SADE did differently**

- 19 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → Skill → Bash → Skill → Skill → … (5 more) … → Bash → Bash → Skill → Bash → Bash → ToolSearch → submit).
- Decisive reasoning (last thinking before `submit`):  
  > …tablished TCP connections   3. `web_server_0` shows `tcp_estab_spike`, `tcp_timewait_spike`, `socket_total_spike` with load average ~9 and 955 established connections, which matches the `web_dos_attack` fingerprint exactly - the attacker is flooding the victim server with HTTP requests, causing socket and CPU pressure. According to the resource-contention-skill, the faulty device is the victim server `web_server_0`, not the attacker.  Now let me verify this explains all the anomalies. The elevated latencies from `host_2_4_4_4` to other hosts stem from it running 1000 concurrent connections under heavy load, which delays its ICMP responses. The neighboring hosts on the same switch (`host_2_4…

---

## Case 79: `web_dos_attack` on `rip_small_internet_vpn` (l)

**Ground truth.** root_cause_name = `['web_dos_attack']`, faulty_devices = `['web_server_4_1']`.

| Agent | session_id | final | submission | failure mode |
|---|---|---:|---|---|
| **ReAct (GPT-5)** | `0425222646` | 1 | `is_anomaly=True`, `root_cause_name=['bgp_blackhole_route_leak']`, `faulty_devices=['external_router_1']` | wrong family + wrong device |
| **CC-Baseline** | `0427061626` | 1 | _no submit() call — agent never finalised a diagnosis_ | no submission |
| **SADE** | `0429192631` | 5 | `is_anomaly=True`, `root_cause_name=['web_dos_attack']`, `faulty_devices=['web_server_4_1']` | — |

**Why each baseline failed**

- **ReAct (GPT-5)** (25 tool calls). Submitted root_cause_name=['bgp_blackhole_route_leak'], faulty_devices=['external_router_1']; ground truth root_cause_name=['web_dos_attack'], faulty_devices=['web_server_4_1'].
- **CC-Baseline** (55 tool calls). Agent never called `submit()` — exhausted its turn budget without finalising.

**What SADE did differently**

- 23 tool calls before `submit()` (ToolSearch → list_avail_problems → get_reachability → Skill → Skill → Bash → Bash → … (9 more) … → exec_shell → exec_shell → exec_shell → exec_shell → Skill → ToolSearch → submit).
- Decisive reasoning (last thinking before `submit`):  
  > The resource-contention-skill is clear:  | Direct evidence on one host | Submit | Faulty devices | |---|---|---| | `http_flood_tool` on an attacker host AND the targeted service shows socket or CPU pressure | `web_dos_attack` | the VICTIM server (not the attacker) |  - host_8 is running `ab -n 200000000 -c 1000 -k http://20.0.3.2/` - this is an `http_flood_tool` - web_server_4_1 (20.0.3.2) is the victim showing high RTT (499-529ms) and 25% packet loss   - Root cause is `web_dos_attack` and the faulty device is web_server_4_1, the victim server. Now I'm ready to submit this.

---
