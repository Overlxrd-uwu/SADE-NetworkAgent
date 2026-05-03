#!/usr/bin/env python3
"""
Parse oversized MCP tool output files saved by Claude Code.

When an MCP tool (e.g. get_reachability) returns data exceeding the
Claude Code token limit, the CLI saves it to a .txt file. This script
reads that file and extracts only the anomalies/failures — so the agent
gets a compact summary instead of wasting turns trying to Read the raw file.

Usage (from Bash tool inside the agent):
    python parse_large_output.py <saved_file_path> [--type reachability|generic]

Output: compact text summary printed to stdout.
"""

import argparse
import json
import sys
from collections import defaultdict


def _parse_ipv4(ip_value):
    """Return IPv4 octets for a host inventory value like '10.2.1.53'."""
    if ip_value is None:
        return None

    text = str(ip_value).strip()
    if "/" in text:
        text = text.split("/", 1)[0]

    parts = text.split(".")
    if len(parts) != 4:
        return None

    try:
        octets = tuple(int(part) for part in parts)
    except ValueError:
        return None

    if any(octet < 0 or octet > 255 for octet in octets):
        return None

    return octets


def _format_host_inventory(hosts):
    """
    Build compact subnet-oriented host inventory lines.

    This keeps the addressing signal that matters for quiet host-IP faults while
    staying much smaller than the raw host map.
    """
    prefix_groups = defaultdict(list)
    non_ipv4_hosts = []

    for host_name, host_ip in sorted(hosts.items()):
        octets = _parse_ipv4(host_ip)
        if octets is None:
            non_ipv4_hosts.append((host_name, host_ip))
            continue
        prefix = ".".join(str(octet) for octet in octets[:3])
        prefix_groups[prefix].append(
            {
                "host": host_name,
                "ip": str(host_ip),
                "last_octet": octets[3],
            }
        )

    outlier_candidates = []
    subnet_lines = []

    def sort_prefix(prefix):
        return tuple(int(part) for part in prefix.split("."))

    for prefix in sorted(prefix_groups.keys(), key=sort_prefix):
        entries = sorted(prefix_groups[prefix], key=lambda item: (item["last_octet"], item["host"]))
        suffixes = [entry["last_octet"] for entry in entries]

        if len(entries) <= 8:
            members = ", ".join(f"{entry['host']}={entry['ip']}" for entry in entries)
            subnet_lines.append(f"  {prefix}.* ({len(entries)} hosts): {members}")
        else:
            suffix_preview = ", ".join(str(suffix) for suffix in suffixes[:10])
            subnet_lines.append(
                f"  {prefix}.* ({len(entries)} hosts): last octets [{suffix_preview}"
                + (", ..." if len(suffixes) > 10 else "")
                + "]"
            )

        # Detect a single last-octet outlier split away from a tight peer cluster.
        if len(entries) >= 3:
            gaps = [
                (entries[i + 1]["last_octet"] - entries[i]["last_octet"], i)
                for i in range(len(entries) - 1)
            ]
            max_gap, gap_index = max(gaps, key=lambda item: item[0])
            left = entries[: gap_index + 1]
            right = entries[gap_index + 1 :]

            def cluster_span(cluster):
                if len(cluster) <= 1:
                    return 0
                return cluster[-1]["last_octet"] - cluster[0]["last_octet"]

            if max_gap >= 16:
                if len(left) == 1 and len(right) >= 2 and cluster_span(right) <= 8:
                    peer_suffixes = ", ".join(str(entry["last_octet"]) for entry in right)
                    outlier_candidates.append(
                        f"  {left[0]['host']}={left[0]['ip']} is isolated from same-/24 peers "
                        f"in {prefix}.* (peer last octets: {peer_suffixes})"
                    )
                elif len(right) == 1 and len(left) >= 2 and cluster_span(left) <= 8:
                    peer_suffixes = ", ".join(str(entry["last_octet"]) for entry in left)
                    outlier_candidates.append(
                        f"  {right[0]['host']}={right[0]['ip']} is isolated from same-/24 peers "
                        f"in {prefix}.* (peer last octets: {peer_suffixes})"
                    )

    if non_ipv4_hosts:
        preview = ", ".join(f"{host}={ip}" for host, ip in non_ipv4_hosts[:8])
        subnet_lines.append(
            f"  Non-IPv4/unparsed inventory entries: {preview}"
            + (" ..." if len(non_ipv4_hosts) > 8 else "")
        )

    return subnet_lines, outlier_candidates


def _format_full_host_inventory(hosts):
    """Build a complete host=ip inventory sorted by IPv4, then host name."""

    def host_sort_key(item):
        host_name, host_ip = item
        octets = _parse_ipv4(host_ip)
        if octets is None:
            return (1, str(host_ip), host_name)
        return (0, *octets, host_name)

    return [f"  {host_name}={host_ip}" for host_name, host_ip in sorted(hosts.items(), key=host_sort_key)]


# Parse the too large reachability output: extract failures, anomalies, and a compact host inventory summary.
def parse_reachability(file_path: str) -> str:
    """Parse get_reachability() output: extract failures, anomalies, host list."""
    with open(file_path, "r", encoding="utf-8-sig") as f:
        data = json.load(f)

    result_str = data.get("result", data) if isinstance(data, dict) else data
    if isinstance(result_str, str):
        inner = json.loads(result_str)
    else:
        inner = result_str

    hosts = inner.get("hosts", {})
    results = inner.get("results", [])

    duplicate_host_ips = defaultdict(list)
    for host_name, host_ip in hosts.items():
        duplicate_host_ips[str(host_ip)].append(host_name)
    duplicate_host_ips = {
        host_ip: sorted(host_names)
        for host_ip, host_names in duplicate_host_ips.items()
        if host_ip and len(host_names) > 1
    }

    # Categorize results
    failures = []
    anomalies = []
    suspicious = []
    ok_count = 0

    for r in results:
        loss = r.get("loss_percent")
        status = (r.get("status") or "").strip().lower()
        rtt_avg = r.get("rtt_avg_ms")

        # Explicitly bad results.
        if status == "fail" or loss == 100:
            failures.append(r)
            continue

        # Partial loss / slow paths.
        if isinstance(loss, (int, float)) and loss > 0:
            anomalies.append(r)
            continue
        if isinstance(rtt_avg, (int, float)) and rtt_avg > 100:
            anomalies.append(r)
            continue

        # Non-ok status or incomplete measurements are suspicious even when they
        # don't fit the classic "loss/rtt" buckets. These rows used to be
        # counted as OK and could hide a broken or overloaded source host.
        if status and status != "ok":
            suspicious.append(r)
            continue
        if any(r.get(field) is None for field in ("tx", "rx", "loss_percent", "rtt_avg_ms")):
            suspicious.append(r)
            continue

        if status == "ok":
            ok_count += 1
            continue

        # Missing status should not be summarized as healthy.
        suspicious.append(r)

    total_hosts = len(hosts.keys()) if isinstance(hosts, dict) else len(hosts)
    suspicious_by_src = defaultdict(list)
    suspicious_by_dst = defaultdict(list)
    for row in suspicious:
        if row.get("src"):
            suspicious_by_src[row["src"]].append(row)
        if row.get("dst"):
            suspicious_by_dst[row["dst"]].append(row)

    host_lines = _format_full_host_inventory(hosts)
    subnet_lines, addressing_outliers = _format_host_inventory(hosts)

    lines = []
    lines.append(f"=== REACHABILITY SUMMARY ===")
    lines.append(f"Total hosts: {total_hosts}")
    lines.append(f"Total tests: {len(results)}")
    lines.append(
        "OK: "
        f"{ok_count} | Failures (100% loss): {len(failures)} | "
        f"Anomalies (partial loss or high RTT): {len(anomalies)} | "
        f"No-response rows (status!=ok or missing tx/rx/loss/rtt — these ARE evidence of intermittent loss / link flap, NOT measurement artifacts): {len(suspicious)}"
    )
    lines.append(f"Potential duplicate IP groups in host inventory: {len(duplicate_host_ips)}")
    lines.append("")

    if duplicate_host_ips:
        lines.append("--- POTENTIAL HOST-IP CONFLICTS (inventory-level identity clash) ---")
        for host_ip, host_names in sorted(duplicate_host_ips.items()):
            lines.append(f"  {host_ip} is claimed by: {', '.join(host_names)}")
            overlap_notes = []
            for host_name in host_names:
                src_hits = len(suspicious_by_src.get(host_name, []))
                dst_hits = len(suspicious_by_dst.get(host_name, []))
                if src_hits or dst_hits:
                    overlap_notes.append(
                        f"{host_name} overlaps suspicious reachability rows "
                        f"(src_hits={src_hits}, dst_hits={dst_hits})"
                    )
            for note in overlap_notes:
                lines.append(f"    {note}")
        lines.append("  NEXT STEP: run get_host_net_config() on the hosts sharing the same IP and L2 inventory to check for IP conflicts, ARP anomalies, or other identity issues.")
        lines.append("")

    clustered_suspicious_sources = sorted(
        (
            (src_host, len(rows))
            for src_host, rows in suspicious_by_src.items()
            if len(rows) >= 2
        ),
        key=lambda item: (-item[1], item[0]),
    )
    clustered_suspicious_destinations = sorted(
        (
            (dst_host, len(rows))
            for dst_host, rows in suspicious_by_dst.items()
            if len(rows) >= 2
        ),
        key=lambda item: (-item[1], item[0]),
    )

    if clustered_suspicious_sources or clustered_suspicious_destinations:
        lines.append("--- REACHABILITY TRIAGE TARGETS ---")
        for src_host, row_count in clustered_suspicious_sources[:5]:
            lines.append(
                f"  Source-focused suspect: {src_host} appears in {row_count} suspicious rows"
            )
        for dst_host, row_count in clustered_suspicious_destinations[:5]:
            lines.append(
                f"  Destination-focused suspect: {dst_host} appears in {row_count} suspicious rows"
            )
        primary_src = None
        primary_src_count = 0
        if clustered_suspicious_sources:
            primary_src, primary_src_count = clustered_suspicious_sources[0]

        primary_dst = None
        primary_dst_count = 0
        if clustered_suspicious_destinations:
            primary_dst, primary_dst_count = clustered_suspicious_destinations[0]

        if primary_dst and primary_dst_count > primary_src_count:
            lines.append(
                f"  NEXT STEP: inspect {primary_dst} once locally, then check the first shared router "
                "or core router on that path with nft list ruleset before broader OSPF or service checks."
            )
        elif primary_src:
            lines.append(
                f"  NEXT STEP: complete the suspect-host local pair on {primary_src}: "
                "get_host_net_config() plus `ip addr; ip route; ip neigh; ip link`, then compare it "
                "to one healthy same-subnet peer before any broader service checks."
            )
        elif primary_dst:
            lines.append(
                f"  NEXT STEP: inspect the path to {primary_dst}, including one implicated router ACL check, "
                "before broader service checks."
            )
        lines.append("")

    if failures:
        lines.append("--- FAILURES (100% packet loss) ---")
        for r in failures:
            lines.append(f"  {r['src']} -> {r['dst']} ({r.get('dst_ip','?')}) | loss={r['loss_percent']}% status={r.get('status','?')}")
        lines.append("")

    if anomalies:
        lines.append("--- ANOMALIES (partial loss or RTT > 100ms) ---")
        for r in anomalies:
            lines.append(f"  {r['src']} -> {r['dst']} ({r.get('dst_ip','?')}) | loss={r['loss_percent']}% rtt_avg={r.get('rtt_avg_ms','?')}ms")
        lines.append("")

    if suspicious:
        lines.append("--- SUSPICIOUS (non-ok status or incomplete measurements) ---")
        for r in suspicious:
            lines.append(
                f"  {r['src']} -> {r['dst']} ({r.get('dst_ip','?')}) | "
                f"status={r.get('status','?')} tx={r.get('tx','?')} rx={r.get('rx','?')} "
                f"loss={r.get('loss_percent','?')} rtt_avg={r.get('rtt_avg_ms','?')}"
            )
        lines.append("")

    if not failures and not anomalies and not suspicious:
        lines.append("ALL TESTS PASSED - no reachability issues were surfaced in the sampled ping matrix.")
        lines.append("Do NOT treat this as proof that the network is healthy; quiet L2/L3 or qdisc faults can still be present.")
        lines.append("")
    elif suspicious and not failures and not anomalies:
        lines.append("No classic ping failures detected, but suspicious/incomplete reachability rows are present.")
        lines.append("Treat the affected source/destination devices as investigation targets instead of assuming the network is healthy.")
        lines.append("Do NOT call this result 'mostly clean' and do NOT replace suspect-host local checks with broad HTTP or service sweeps yet.")
        lines.append("")
    if duplicate_host_ips:
        lines.append("Duplicate IP ownership in the reachability host inventory is NOT a sampling artifact.")
        lines.append("This pattern strongly suggests host_ip_conflict or another identity/addressing fault.")
        lines.append("")

    if addressing_outliers:
        lines.append("--- ADDRESSING OUTLIER CANDIDATES ---")
        lines.extend(addressing_outliers[:12])
        lines.append(
            "  NEXT STEP: inspect the outlier host with get_host_net_config() plus "
            "`ip addr; ip route; ip neigh; ip link`, then compare it to one healthy same-subnet peer "
            "before deeper service checks."
        )
        lines.append("")

    lines.append(f"--- FULL HOST/IP INVENTORY ({total_hosts} hosts) ---")
    lines.extend(host_lines)
    lines.append("")

    lines.append(f"--- HOST/IP SUBNET PREVIEW ({total_hosts} hosts) ---")
    preview_limit = min(len(subnet_lines), 20)
    lines.extend(subnet_lines[:preview_limit])
    if len(subnet_lines) > preview_limit:
        lines.append(f"  ... ({len(subnet_lines) - preview_limit} more subnet groups omitted)")

    return "\n".join(lines)


def _looks_like_reachability(file_path: str) -> bool:
    """Return True if the saved file is a reachability-shaped payload.

    Detection is structural: the inner object carries both a `hosts` mapping
    and a `results` list. `safe_reachability --json` and the MCP
    `get_reachability` tool share this shape, so either overflow lands in the
    reachability formatter.
    """
    try:
        with open(file_path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return False

    inner = data.get("result", data) if isinstance(data, dict) else data
    if isinstance(inner, str):
        try:
            inner = json.loads(inner)
        except (json.JSONDecodeError, TypeError):
            return False

    return (
        isinstance(inner, dict)
        and isinstance(inner.get("hosts"), dict)
        and isinstance(inner.get("results"), list)
    )


def _read_inner_text(file_path: str) -> str | None:
    """Return the inner string payload from a saved tool-output file, or None."""
    try:
        with open(file_path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        try:
            with open(file_path, "r", encoding="utf-8-sig") as f:
                return f.read()
        except OSError:
            return None
    inner = data.get("result", data) if isinstance(data, dict) else data
    if isinstance(inner, str):
        return inner
    return None


def _summarize_flags_line(flags_line: str) -> str:
    """Compress a `Flags: ...` line to per-type counts.

    The per-client Flags line lists every flagged hostname/URL (e.g.
    `Flags: dns_problem:web0.pod0, dns_problem:web1.pod0, http_non_ok:...`),
    which duplicates the DNS/HTTP outcome groups already emitted earlier.
    Replace it with one count per flag type so the per-client summary scales
    with topology size instead of with hostname count.
    """
    body = flags_line.split(":", 1)[1].strip() if ":" in flags_line else ""
    if not body or body.lower() == "none":
        return "Flags: none"
    counts: dict[str, int] = defaultdict(int)
    for token in body.split(","):
        flag = token.strip().split(":", 1)[0]
        if flag:
            counts[flag] += 1
    if not counts:
        return "Flags: none"
    parts = ", ".join(f"{count} {flag}" for flag, count in sorted(counts.items()))
    return f"Flags: {parts}"


def _looks_like_service_snapshot(file_path: str) -> bool:
    """Return True if the saved file is a service_snapshot text payload.

    The helper's text output (the default mode) starts with the
    `=== SERVICE SNAPSHOT ===` banner, regardless of lab. JSON output of the
    same helper falls through to the generic parser.
    """
    text = _read_inner_text(file_path)
    if not isinstance(text, str):
        return False
    return text.lstrip().startswith("=== SERVICE SNAPSHOT ===")


def parse_service_snapshot(file_path: str) -> str:
    """Parse oversized service_snapshot text output.

    The bulk of the size comes from per-client blocks: each client emits one
    DNS row + one HTTP row per published hostname, so on a 4-pod x 7-web lab
    the per-client section alone is ~25–30 kB. The header already aggregates
    the same outcomes through the resolver/DNS/HTTP outcome groups, which is
    the section that actually reveals per-zone failure patterns (e.g. one
    pod's DNS resolves while peers return `no_addresses`, fingerprinting a
    server-side `dns_record_error`). The per-service-device blocks are small
    and carry the named/listener/process evidence used by `dns-fault-skill`.

    Strategy: emit the header (through the `Suspect clients:` line) plus all
    per-service-device blocks in full, then condense each per-client block to
    a single line listing its nameservers and aggregate flags. The agent can
    rerun `service_snapshot --client <name>` to see raw per-row addresses for
    a specific client when the GROUPS view is not enough.
    """
    text = _read_inner_text(file_path)
    if not isinstance(text, str):
        raise ValueError("service_snapshot payload not found in saved file")

    lines = text.splitlines()

    suspect_idx: int | None = None
    for idx, line in enumerate(lines):
        if line.startswith("Suspect clients:"):
            suspect_idx = idx
            break
    if suspect_idx is None:
        # Missing the marker - unknown variant. Fall back to emitting the
        # whole text; the caller will still see more than the 3 kB generic cap.
        return "\n".join(lines)

    output: list[str] = list(lines[: suspect_idx + 1])

    body = lines[suspect_idx + 1 :]
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in body:
        if not line.strip():
            if current:
                blocks.append(current)
                current = []
            continue
        if not line.startswith((" ", "\t")):
            if current:
                blocks.append(current)
            current = [line]
        else:
            if current:
                current.append(line)
    if current:
        blocks.append(current)

    client_blocks: list[list[str]] = []
    service_blocks: list[list[str]] = []
    for block in blocks:
        is_service = any(
            "Localhost HTTP:" in row or "Processes visible:" in row for row in block
        )
        is_client = any(
            row.lstrip().startswith(("DNS ", "HTTP ", "Nameservers:")) for row in block
        )
        if is_service and not is_client:
            service_blocks.append(block)
        elif is_client:
            client_blocks.append(block)

    if client_blocks:
        output.append("")
        output.append(
            f"Per-client blocks ({len(client_blocks)} clients) condensed - the "
            "DNS/HTTP outcome groups above already aggregate the same per-host/per-URL "
            "results across clients. To see raw per-row addresses for one client, "
            "rerun `python ../../h.py service_snapshot --client <name>`."
        )
        for block in client_blocks:
            device = block[0].strip()
            ns_line = next(
                (row.strip() for row in block if row.lstrip().startswith("Nameservers:")),
                "Nameservers: (none)",
            )
            flags_line = next(
                (row.strip() for row in block if row.lstrip().startswith("Flags:")),
                "Flags: none",
            )
            output.append(f"- {device}: {ns_line}; {_summarize_flags_line(flags_line)}")

    if service_blocks:
        output.append("")
        for block in service_blocks:
            output.extend(block)
            output.append("")

    return "\n".join(output).rstrip() + "\n"


def parse_generic(file_path: str) -> str:
    """Parse any oversized JSON output: print structure + first N entries."""
    with open(file_path, "r", encoding="utf-8-sig") as f:
        data = json.load(f)

    result = data.get("result", data) if isinstance(data, dict) else data

    if isinstance(result, str):
        try:
            result = json.loads(result)
        except (json.JSONDecodeError, TypeError):
            # Plain text — return truncated
            if len(result) > 3000:
                return f"[TEXT, {len(result)} chars]\n{result[:3000]}\n... [TRUNCATED]"
            return result

    if isinstance(result, dict):
        lines = [f"JSON object with keys: {list(result.keys())}"]
        for k, v in result.items():
            if isinstance(v, list):
                lines.append(f"  {k}: list[{len(v)}] — first entry: {json.dumps(v[0], default=str)[:200] if v else 'empty'}")
            elif isinstance(v, dict):
                lines.append(f"  {k}: dict with keys {list(v.keys())[:10]}")
            else:
                lines.append(f"  {k}: {str(v)[:200]}")
        return "\n".join(lines)

    if isinstance(result, list):
        lines = [f"JSON array with {len(result)} entries"]
        for item in result[:5]:
            lines.append(f"  {json.dumps(item, default=str)[:200]}")
        if len(result) > 5:
            lines.append(f"  ... ({len(result) - 5} more entries)")
        return "\n".join(lines)

    return str(result)[:3000]


def main():
    parser = argparse.ArgumentParser(description="Parse oversized MCP tool output")
    parser.add_argument("file_path", help="Path to the saved .txt file")
    parser.add_argument(
        "--type",
        choices=["reachability", "service_snapshot", "generic", "auto"],
        default="auto",
        help=(
            "Output type for specialized parsing. Default `auto` picks "
            "`reachability` when the payload carries `hosts` + `results` "
            "(covers both get_reachability and safe_reachability --json), "
            "`service_snapshot` when the text starts with the "
            "`=== SERVICE SNAPSHOT ===` banner, and falls back to `generic` "
            "otherwise."
        ),
    )
    args = parser.parse_args()

    mode = args.type
    if mode == "auto":
        if _looks_like_reachability(args.file_path):
            mode = "reachability"
        elif _looks_like_service_snapshot(args.file_path):
            mode = "service_snapshot"
        else:
            mode = "generic"

    try:
        if mode == "reachability":
            print(parse_reachability(args.file_path))
        elif mode == "service_snapshot":
            print(parse_service_snapshot(args.file_path))
        else:
            print(parse_generic(args.file_path))
    except Exception as e:
        print(f"ERROR parsing file: {e}", file=sys.stderr)
        # Fallback: print file size only — do NOT dump raw content
        # (raw JSON confuses the agent into trying to Read the file)
        try:
            with open(args.file_path, "r", encoding="utf-8-sig") as f:
                content = f.read()
            print(f"[Fallback] File size: {len(content)} chars. Parse failed: {e}")
            print("Do NOT try to Read this file — it is too large.")
            print("Proceed with diagnosis using other tools (exec_shell, etc).")
        except Exception:
            print(f"Could not read file. Proceed with other diagnostic tools.")


if __name__ == "__main__":
    main()
