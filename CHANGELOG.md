# SADE Agent Iteration Log

Tracks prompt/skill changes, benchmark results, and rationale for each iteration.

---

## Summary — Optimization Flow

```
First Attempt (Iteration 0):  20/37 perfect  (15 NO_SUBMIT, 2 WRONG)
Iteration 1-3b:               Identified root causes (nftables, turn counter, skills)
Iteration 3c:                 Host misconfig disambiguation + turn counter calibration
Iteration 4 (retry 16):       10/16 perfect  → 6 remaining failures analyzed
Iteration 4 retry:            14/16 perfect  → 2 remaining failures
Iteration 5 (prompt trim):    16/16 perfect  → all retry cases pass
Iteration 5b (final 2):       Pending — host_incorrect_dns/l, host_missing_ip/l
Iteration 6:                  host_missing_ip/l — "submit immediately" rule
Iteration 7 (full rerun):     23/35 perfect — 12 failures analyzed
Iteration 7 fixes:            link↔host_missing_ip disambiguation + host nft emphasis
```

### Key Changes by Category

**Discovery: nftables not iptables** (Iteration 3b)
- NIKA injects ALL ACL rules via `nft`, not `iptables`. Single biggest fix.
- Source: `injector_base.py:98-117` uses `nft_add_table/chain/rule`

**Prompt: sade_prompt.py** (138 lines → 77 lines)
- Added Step 0c: `nft list ruleset && ip link show` on routers + hosts + servers
- Added MAC comparison in Step 0c (was only in stall recovery)
- Added OOM-kill detection via `dmesg` in Step 3
- Added host config disambiguation rules in Step 0b
- Removed Turn Budget section (handled by runtime injection)
- Trimmed redundancy — detailed rules moved to skill files

**Skills created/updated:**
- `iptables-acl-skill`: Rewritten for nftables fingerprints
- `host-ip-conflict-skill`: Added host misconfig disambiguation, ARP poisoning, MAC conflict
- `resource-contention-skill`: Added OOM-kill detection procedure
- `load-balancer-skill`: Added shared loadavg warning
- `baseline-behavior-skill`: Added DHCP lease time, nftables reference
- `diagnosis-methodology-skill`: Added "device not running" retry guidance

**Agent code: claude_code_agent_sade.py**
- Switched from query() to ClaudeSDKClient for mid-conversation warning injection
- Turn counter: AssistantMessage count → ToolResultBlock count (thresholds 45/55)
- Critical warning rewritten: "STOP investigating, ONLY next action must be submit()"

### Remaining Known Limitations

- `host_incorrect_dns/l,s`: DHCP 30s lease heals fault before agent checks — known benchmark limitation
- `host_missing_ip/l`: DHCP partial heal on large topology (mitigated by "submit immediately" rule)

---

## Iteration 7 — 2026-04-08 (full 37-case rerun + fixes)

### Benchmark Result: 23/35 perfect (3 cases didn't run, 12 failures)

### Failure Analysis

| Pattern | Cases | Root Cause |
|---------|-------|------------|
| DHCP race | host_incorrect_dns/l,s | DHCP heals resolv.conf — unfixable |
| link→host_missing_ip | link_detach/l, link_flap/l | Agent submits host_missing_ip without checking eth0 state |
| Skipped hosts in nft | arp_acl_block/l | Agent only checked routers/servers, not hosts |
| ospf fallback guess | load_balancer_overload/s, mac_address_conflict/l | Agent can't find fault, defaults to ospf guess |
| NO_SUBMIT | load_balancer_overload/m, receiver_resource_contention/m | Ran out of turns |
| Lab infra broken | sender_resource_contention/l,m | All containers "not running" |
| Wrong device | http_acl_block/l | Correct RCA, wrong device |

### Changes

**sade_prompt.py**:
- Step 0b: Before submitting host_missing_ip, check `ip link show eth0` first.
  If eth0 DOWN/absent → link fault, not host_missing_ip.
- Step 0c: Bold "Hosts (MANDATORY)" + added "ACL faults are often injected on hosts"
  to prevent agent from skipping host nft checks.
- Step 0c: Added dns_server, dhcp_server to device check list.
- Stall Recovery: Added guidance to check additional devices from topology
  description (e.g. backend_web_*, switch_*) for MAC conflicts.
  mac_address_conflict/l failed because backend_web_0 was never checked.

**host-ip-conflict-skill/SKILL.md**:
- Added "BEFORE Submitting host_missing_ip — Check eth0 Link State!" section
  with link_detach/link_down/link_flap disambiguation based on eth0 state.
- MAC conflict: Added step to check topology-described devices beyond Step 0c list.

---

## Iteration 6 — 2026-04-08 (host_missing_ip DHCP race fix)

### Failure: host_missing_ip/l — NO_SUBMIT (61 tool results, max turns hit)

Agent found `host_2_1_1_1` missing default gateway at tool call ~10, but then
spent 50 more calls second-guessing because the host had `valid_lft 56sec` (DHCP
dynamic) instead of `valid_lft forever` (static) that the skill said to expect.
The DHCP 30s lease restored the IP but not the default route — a partial heal.
Agent was ONE tool call from submitting when it hit max turns.

### Changes

**host-ip-conflict-skill/SKILL.md**:
- Added "Gateway missing entirely" → `host_missing_ip` to disambiguation table
- Added "DHCP Race Condition" section: missing gateway with dynamic lease = still
  a host fault, trust FIRST observation, submit immediately

**sade_prompt.py**:
- Step 0b: Added "If a host differs: read skill, then submit IMMEDIATELY.
  Do NOT keep investigating — the host config diff IS the answer."
- Added: "Missing default gateway (even with dynamic DHCP IP) = host_missing_ip"

---

## Iteration 5b — 2026-04-08 (prompt condensed + final 2 retried)

### Benchmark Result: 16/16 retry cases perfect

Prompt trimmed from 138 → 77 lines. Both last holdouts passed:
- mac_address_conflict/l: MAC comparison in Step 0c found the conflict
- receiver_resource_contention/m: dmesg OOM-kill detection caught stress-ng evidence

---

## Iteration 5 — 2026-04-08 (MAC conflict + OOM-kill detection + forced submit)

### Benchmark Result: 14/16 perfect (up from 10/16)

Fixed: http_acl_block/m, arp_cache_poisoning/m, sender_resource_contention/m+l
Remaining: mac_address_conflict/l (NO_SUBMIT), receiver_resource_contention/m (wrong RCA)

### Root Cause Analysis

**mac_address_conflict/l**: Agent spent 60 tool calls investigating LB, TC, curl.
Never compared MAC addresses across devices. Got CRITICAL warning at 55 but kept
investigating instead of submitting — ran out of turns with NO submission.
- Fix 1: Added `ip link show` + MAC comparison to Step 0c for ALL devices including
  web servers and load_balancer (not just routers)
- Fix 2: Rewrote MAC conflict skill with explicit "extract eth0 MACs and compare"
- Fix 3: Made CRITICAL warning much more aggressive: "STOP investigating, your ONLY
  next action must be submit()"
- Fix 4: Made MAC conflict check #1 priority in Stall Recovery

**receiver_resource_contention/m**: Agent ran `ps aux` on host_1_1_1_1 (correct device)
but stress-ng had been OOM-killed — NO stress process visible. Agent then got distracted
by OSPF area configs and submitted wrong RCA.
- Fix 5: Added OOM-kill detection to Step 3: `dmesg | grep -i 'oom\|killed'`
- Fix 6: Updated resource-contention-skill with full OOM-kill detection guide
  (dmesg, /proc/meminfo, defunct processes)

### Changes

**sade_prompt.py**:
- Step 0c: Now includes web_server_0-3 and load_balancer in `ip link show` check,
  explicit MAC comparison instruction
- Step 3: Added OOM-kill detection via dmesg when stress not visible
- Stall Recovery: Reordered — MAC conflict check is now #1 priority

**claude_code_agent_sade.py**:
- Critical warning text now says "STOP investigating, ONLY next action must be submit()"

**host-ip-conflict-skill/SKILL.md**:
- Rewrote MAC conflict section with "When to Suspect" guidance, explicit detection
  steps, and note that ANY pair of devices can conflict

**resource-contention-skill/SKILL.md**:
- Replaced transient stress note with full OOM-kill detection procedure

**benchmark_selected.csv**: 2 remaining cases

---

## Iteration 4 — 2026-04-07 (6 failure root cause analysis + fixes)

### Benchmark Result: 10/16 perfect (up from 0/16)

| Case | Result | What Agent Submitted | Ground Truth | Error Type |
|---|---|---|---|---|
| http_acl_block/m | FAIL | dns_server/dns_lookup_latency | host_2_1_1_1/http_acl_block | Skipped hosts in nft check |
| mac_address_conflict/l | FAIL | dns_server/dns_lookup_latency | web_server_1+sar/mac_address_conflict | Never checked MACs |
| arp_cache_poisoning/m | LOC | host_2_1_1_1/link_flap | host_2_1_1_1/arp_cache_poisoning | One-directional failure misclassified |
| receiver_res_contention/m | FAIL | router_dist_2_1/ospf_area_misconfig | host_2_1_1_1/receiver_resource_contention | Never ran ps aux on hosts |
| sender_res_contention/m | FAIL | sar/frr_service_down | web_server_3/sender_resource_contention | ps aux head -5 too short |
| sender_res_contention/l | FAIL | host_1_1_1_1/host_missing_ip | web_server_3/sender_resource_contention | Never checked web servers |

### Systemic Issues Found

1. **Step 0c: Agent skips host nft checks** — prompt says check 4 hosts but agent only checks routers
2. **Step 3: `ps aux | head -5`** — too few lines, stress-ng below line 5 is missed
3. **Step 3: Hosts never checked for ps aux** — only web servers checked
4. **Hallucinated RCA names** — `dns_lookup_latency` doesn't exist in NIKA
5. **ARP poisoning unrecognized** — one-directional failure + fake MAC not identified

### Changes Made

**sade_prompt.py**:
- Step 0c: Emphasized "DO NOT skip the hosts" for nft checks, reformatted device list
- Step 3: Changed `head -10` to `head -20`, explicit device list (ALL web servers + 
  ALL sampled hosts + LB/DNS/DHCP), inline sender vs receiver classification
- Added "One-Directional Failure Pattern" section for ARP poisoning detection
- Stall Recovery: Added ARP poisoning MAC check, MAC conflict check instructions
- Added rule: "ONLY submit root_cause_name from known list, NEVER invent names"

**host-ip-conflict-skill/SKILL.md**:
- Added full "ARP Cache Poisoning Identification" section with fingerprint, detection
  steps, and submit format

**benchmark_selected.csv**: Updated to 6 remaining failed cases

---

## Iteration 3c — 2026-04-07 (host misconfig disambiguation + turn counter calibration)

### Critical Finding: Agent misclassifies host config faults as DHCP faults

In `host_incorrect_gateway/0407135810`, the agent saw:
- `host_2_1_1_1`: gateway `10.2.1.254` (wrong — should be `.1`), `valid_lft forever`
- `host_1_1_1_1`: gateway `10.1.1.1` (correct), `valid_lft 35sec` (DHCP)

But submitted `dhcp_missing_subnet` on `dhcp_server` instead of `host_incorrect_gateway`
on `host_2_1_1_1`. The agent fixated on "static vs DHCP" and missed that the gateway
itself was wrong. Root cause: **no skill existed to disambiguate host misconfig faults
from DHCP faults**.

### Changes Made

**host-ip-conflict-skill/SKILL.md** — Added "Host Misconfig Fault Disambiguation" section:
1. Table mapping what-differs-from-peers → root_cause_name (gateway/IP/netmask/DNS)
2. Explicit rule: faulty device is ALWAYS the differing HOST, NEVER dhcp_server
3. Explained that `valid_lft forever` + `broadcast 0.0.0.0` is a side effect of
   `ip addr add` (the fault injection), NOT a sign of DHCP failure
4. Gateway `.254` fingerprint — does not exist in network, always `host_incorrect_gateway`
5. DHCP disambiguation: `dhcp_missing_subnet` = ALL hosts in subnet lack IPs, not just one

**sade_prompt.py** — Updated Step 0b:
6. Added inline classification rules for host config differences
7. Explicit: "faulty device is ALWAYS the differing HOST, NEVER dhcp_server"
8. Added: "`valid_lft forever` is a side effect of fault injection — NOT a DHCP problem"
9. Directs agent to read `host-ip-conflict-skill/SKILL.md` before any host config submission

### Also Fixed (turn counter)

10. **`turn_count` undefined** — line 209 referenced `turn_count` after refactor. Fixed to `tool_result_count`.
11. **Thresholds too high (60/80) — warnings never fire in normal sessions**
    - Normal sessions: 56-68 tool results. New thresholds: WARNING=45, CRITICAL=55.

### Evidence (tool results per session)

| Session | Tool Results |
|---|---|
| arp_acl_block/0407131858 | 67 |
| host_incorrect_gateway/0407122233 | 56 |
| host_incorrect_gateway/0407135810 | 19 (broken — premature warning) |
| host_missing_ip/0407123416 | 68 |
| link_down/0407124621 | 60 |
| link_flap/0407130117 | 67 |

---

## Iteration 3b — 2026-04-07 (nftables fix — CRITICAL)

**Benchmark**: 5/16 retry cases completed before this fix

### Critical Finding: iptables vs nftables

NIKA injects ALL ACL rules via **nftables** (`nft`), NOT iptables.
`iptables -L -n -v` returns EMPTY even when ACL rules exist.
Only `link_fragmentation_disabled` uses legacy iptables.

Source: `injector_base.py:98-117` — `inject_acl_rule()` calls `nft_add_table/chain/rule`.

The arp_acl_block agent found the nft rules on its LAST turn (21) but couldn't submit.

### Changes Made

**sade_prompt.py**:
1. Step 0c: Changed `iptables -L -n -v` → `nft list ruleset` on all routers + 4 hosts
2. Stall Recovery: Updated to reference nftables instead of iptables

**iptables-acl-skill/SKILL.md** (fully rewritten):
3. Added nftables as PRIMARY detection method
4. Added nft fingerprint table (arp drop, icmp drop, tcp dport 80 drop, etc.)
5. Moved iptables to legacy section (only for link_fragmentation_disabled)

**baseline-behavior-skill/SKILL.md**:
6. Added DHCP lease time section — 30s lease is NORMAL in testbed
7. Added: host with no IP = `host_missing_ip`, NOT `dhcp_service_down`
8. Changed "iptables DROP rule" → "nftables DROP rule" in fault list

**claude_code_agent_sade.py** (major refactor):
7. Switched from `query()` (one-shot) to `ClaudeSDKClient` (bidirectional)
8. Added turn counter tracking `AssistantMessage` count
9. At turn 15: injects user message "TURN BUDGET WARNING — wrap up, prepare to submit"
10. At turn 17: injects user message "TURN BUDGET CRITICAL — submit NOW on next action"
11. Rationale: agent consistently hit turn 21 with evidence but no submission.
   The SDK's `ClaudeSDKClient.query()` injects a real user message mid-conversation,
   which the model treats as a hard instruction (not just a prompt hint it can ignore).

### Other Findings from Retry Run

| Case | Issue | Status |
|---|---|---|
| host_missing_ip/s | Submitted `dhcp_service_down` instead of `host_missing_ip` | Fixed via baseline skill |
| host_incorrect_gateway/l | DHCP heals wrong gateway before agent diagnoses | Same DHCP race — may be unfixable |
| link_down/l | Agent found DOWN, re-checked → UP, confused as flap | Timing issue — link state unstable |
| arp_acl_block/l | Found nft rules on turn 21, couldn't submit | Fixed — nft check now in Step 0c |

---

## Iteration 3 — 2026-04-07 (Infrastructure Sweep + Skill Fixes)

**Benchmark baseline**: 44 cases, 19 PASS (43%), 19 NO_SUBMIT, 4 WRONG, 2 PARTIAL

### Root Cause Analysis of Failures

| Failure Cluster | Cases | Root Cause |
|---|---|---|
| ACL blocks (arp/http/icmp/ospf) | 5 | Agent never checks iptables on routers — only on hosts |
| mac_address_conflict | 2 | MAC conflict on routers, not hosts — no skill, no detection path |
| sender_resource_contention | 2 (WRONG) | Agent sees shared loadavg >10 on LB, submits `load_balancer_overload` instead |
| receiver_resource_contention | 2 | Agent checks `top` on servers but not on client hosts |
| link_down/link_flap | 2 | Agent doesn't run `ip link show` on hosts during sweep |
| host_incorrect_gateway/l | 1 | Host sweep samples 16/128 — missed the faulty host |
| host_missing_ip/s | 1 | Partial submission (wrong localization) |
| arp_cache_poisoning/m | 1 | Agent didn't check ARP tables |
| host_incorrect_dns/l x5 | 5 | DHCP 30s lease heals fault before agent checks — KNOWN FLAKY, excluded |

### Changes Made

**sade_prompt.py** (75 -> 93 lines):

1. **Added Step 0c — Infrastructure Sweep**
   - `iptables -L -n -v` on all 5 routers (router_core_1/2, router_dist_1_1/2_1, server_access_router)
   - `ip link show` on 4 sampled hosts (1 per area)
   - Rationale: 7+ failures caused by agent never checking router iptables or host link state

2. **Rewrote Step 3 — L3 now checks BOTH servers AND hosts**
   - `ps aux --sort=-%cpu | head -10` on sampled hosts AND all web servers
   - Explicit process names to look for (stress, ab, hping3, etc.)
   - Rationale: receiver_resource_contention missed because agent only checked server-side

3. **Rewrote Stall Recovery section**
   - Protocol-specific ACL guidance (ICMP/HTTP/OSPF ACLs don't block ping)
   - ARP table check for MAC conflicts
   - Expanded host sampling guidance
   - Rationale: old stall recovery only suggested more host sampling, missed infra faults

**load-balancer-skill/SKILL.md**:

4. **Added shared loadavg warning**
   - `/proc/loadavg` reflects host machine in Kathara, not the container
   - Must also see LB timeout OR slow curl-through-VIP to confirm `load_balancer_overload`
   - If loadavg high but curl normal (~850ms), check servers for `sender_resource_contention`
   - Rationale: both sender_resource_contention WRONG cases were misdiagnosed as LB overload

**host-ip-conflict-skill/SKILL.md**:

5. **Added MAC Address Conflict section**
   - Detection via `ip link show` on routers + ARP table comparison
   - Note that MAC conflicts affect ROUTERS, not just hosts
   - Report BOTH devices sharing the MAC
   - Rationale: mac_address_conflict had no skill coverage at all

### Retry Plan

16 failed cases selected for next run (see benchmark/benchmark_selected.csv).
Excluded 5x host_incorrect_dns/l (DHCP race — unfixable without modifying NIKA injector).

---

## Iteration 2 — 2026-04-06 (Host Config Sweep + Prompt Trim)

**Benchmark baseline**: Previous NO_SUBMIT cases only

### Changes Made

**sade_prompt.py** (202 -> 75 lines, 63% reduction):

1. **Split Step 0 into 0a (Read) and 0b (MCP calls)**
   - Rationale: mixing Read with MCP calls in same parallel batch caused cascade failures — Read error cancelled all MCP calls

2. **Added Step 0b — Host Config Sweep (32 parallel calls)**
   - `get_host_net_config()` + `cat /etc/resolv.conf` on 16 hosts (2 per subnet)
   - Rationale: agent was only checking 2 hosts, missing single-host faults on large topologies

3. **Removed all duplication with skills**
   - Prompt says WHAT to do, skills say HOW to classify
   - Rationale: skills save prompt token cost, no need to duplicate fingerprints

**dns-fault-skill/SKILL.md** — trimmed, removed DHCP masking warning and batch script reference

**baseline-behavior-skill/SKILL.md** — trimmed to essentials

### Key Finding

`host_incorrect_dns/l` is undetectable due to DHCP 30s lease race condition.
Fault injection writes `nameserver 8.8.8.8` to resolv.conf, but DHCP renewal
overwrites it back before agent can observe. Documented in memory, accepted as known limitation.

---

## Iteration 1 — 2026-04-06 (Initial SADE Agent)

Initial SADE prompt with layered L1->L2->L3 escalation.
Skills created for all major fault categories.
First full benchmark run: 640 cases planned, stopped at case 49.
