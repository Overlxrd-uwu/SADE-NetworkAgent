"""Traffic generation (OD-matrix iperf3, web load)."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Literal

import typer

from nika.generator.traffic.od_flows import ODFLowGenerator
from nika.generator.traffic.web_access import WebBrowsingTrafficGenerator
from nika.net_env.net_env_pool import get_net_env_instance, scenario_requires_topo_tier
from nika.utils.session_resolve import resolve_running_session_id
from nika.utils.session_store import SessionStore

traffic_app = typer.Typer(help="Generate traffic in the Kathará lab.")

_TRAFFIC_TYPE_HELP: dict[str, str] = {
    "od": "OD-matrix iperf3 between hosts (--od-json, --mesh-mbps, or --all-to-host + --mbps).",
    "web": "Synthetic web browsing (ab) for scenarios with web_urls.",
}


def _net_env_kwargs_for_scenario(scenario: str, tier: str | None) -> dict[str, Any]:
    if scenario_requires_topo_tier(scenario):
        if not tier:
            raise typer.BadParameter(f"Scenario '{scenario}' requires -t/--tier (s, m, or l).")
        return {"topo_size": tier}
    if tier is not None:
        raise typer.BadParameter(f"Scenario '{scenario}' does not use topology tiers; omit -t/--tier.")
    return {}


def _resolve_lab_and_tier(
    lab: str | None,
    tier: str | None,
) -> tuple[str, str | None]:
    try:
        resolved_id = resolve_running_session_id()
        meta = SessionStore().get_session(resolved_id)
    except (FileNotFoundError, ValueError, OSError, KeyError, TypeError, json.JSONDecodeError):
        if not lab:
            raise typer.BadParameter(
                "No valid running session found. Run `nika env run <scenario>` first, or pass --lab."
            ) from None
        return lab, tier

    resolved_lab = lab or meta.get("scenario_name")
    resolved_tier = tier if tier is not None else meta.get("scenario_topo_size")
    if not resolved_lab:
        raise typer.BadParameter("Session has no scenario_name; run `nika env run` or pass --lab.")
    return resolved_lab, resolved_tier


def _normalize_tier(raw: str | None) -> str | None:
    if raw is None or raw == "":
        return None
    if raw not in ("s", "m", "l"):
        raise typer.BadParameter("Topology tier must be one of: s, m, l.")
    return raw


@traffic_app.command("list")
def traffic_list() -> None:
    """List supported traffic types for `nika traffic run`."""
    for name, desc in sorted(_TRAFFIC_TYPE_HELP.items()):
        typer.echo(f"{name:8}  {desc}")


@traffic_app.command("run")
def traffic_run(
    traffic_type: str = typer.Argument(..., metavar="TYPE", help="od | web"),
    background: bool = typer.Option(
        False,
        "--background/--no-background",
        help="Run traffic in the background where supported (od); web always blocks the CLI.",
    ),
    lab: str | None = typer.Option(None, "--lab", help="Kathará lab name (defaults to current session scenario)."),
    tier: str | None = typer.Option(None, "-t", "--tier", help="Topology tier s, m, or l (when the scenario uses tiers)."),
    # OD (iperf3) shared
    interval: int = typer.Option(5, "--interval", help="iperf3 duration per client run (seconds)."),
    unit: str = typer.Option("M", "--unit", help='OD matrix bitrate unit suffix: "K" or "M" (iperf -b).'),
    udp: bool = typer.Option(True, "--udp/--no-udp", help="Use UDP for iperf3 OD flows."),
    server_args: str = typer.Option("", "--server-args", help="Extra iperf3 server arguments."),
    client_args: str = typer.Option("", "--client-args", help="Extra iperf3 client arguments."),
    od_json: Path | None = typer.Option(None, "--od-json", help="Path to JSON OD matrix: {src: {dst: rate, ...}, ...}."),
    mesh_mbps: int | None = typer.Option(None, "--mesh-mbps", help="Start full mesh among hosts at this many Mbit/s each."),
    all_to_host: str | None = typer.Option(
        None,
        "--all-to-host",
        help="Every other host sends to this host at --mbps (Mbit/s).",
    ),
    mbps: int | None = typer.Option(None, "--mbps", help="Bitrate in Mbit/s for --all-to-host (od mode)."),
    # web-only
    request_delay_min: float = typer.Option(1.0, "--request-delay-min", help="[web] Min pause between page fetches."),
    request_delay_max: float = typer.Option(5.0, "--request-delay-max", help="[web] Max pause between page fetches."),
    pages_min: int = typer.Option(3, "--pages-min", help="[web] Min pages per browsing session."),
    pages_max: int = typer.Option(10, "--pages-max", help="[web] Max pages per browsing session."),
    no_loop: bool = typer.Option(False, "--no-loop", help="[web] Run one browsing session per host then stop."),
) -> None:
    """Start traffic of the given TYPE against the current lab (or ``--lab``)."""
    t = traffic_type.strip().lower()
    if t not in _TRAFFIC_TYPE_HELP:
        raise typer.BadParameter(f"Unknown TYPE {traffic_type!r}; try `nika traffic list`.")

    tier_n = _normalize_tier(tier)
    scenario, tier_resolved = _resolve_lab_and_tier(lab=lab, tier=tier_n)

    if unit not in ("K", "M"):
        raise typer.BadParameter('--unit must be "K" or "M".')
    unit_lit: Literal["K", "M"] = unit  # type: ignore[assignment]

    if t == "web":
        if background:
            raise typer.BadParameter(
                "`web` traffic always blocks this CLI until interrupted; do not pass `--background`."
            )
        kwargs = _net_env_kwargs_for_scenario(scenario, tier_resolved)
        gen = WebBrowsingTrafficGenerator(
            scenario_name=scenario,
            request_delay_range=(request_delay_min, request_delay_max),
            pages_per_session_range=(pages_min, pages_max),
            loop_forever=not no_loop,
            **kwargs,
        )
        asyncio.run(gen.generate_traffic())
        return

    if t == "od":
        kwargs = _net_env_kwargs_for_scenario(scenario, tier_resolved)
        net_env = get_net_env_instance(scenario, **kwargs)
        hosts = list(net_env.hosts)

        od_dict: dict[str, dict[str, int]]

        if od_json is not None:
            raw = json.loads(od_json.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise typer.BadParameter("OD JSON must be an object mapping src -> {dst: int, ...}.")
            od_dict = {}
            for sk, dv in raw.items():
                if not isinstance(dv, dict):
                    raise typer.BadParameter(f"Invalid OD row for {sk!r}.")
                od_dict[str(sk)] = {str(dk): int(val) for dk, val in dv.items()}
            if mesh_mbps is not None or all_to_host is not None or mbps is not None:
                raise typer.BadParameter("Do not combine --od-json with --mesh-mbps / --all-to-host / --mbps.")
        elif mesh_mbps is not None:
            od_dict = {}
            for a in hosts:
                od_dict.setdefault(a, {})
                for b in hosts:
                    if a != b:
                        od_dict[a][b] = mesh_mbps
            if mbps is not None and all_to_host is None:
                raise typer.BadParameter("--mbps is only used with --all-to-host, not with --mesh-mbps.")
        elif all_to_host is not None:
            if mbps is None:
                raise typer.BadParameter("--all-to-host requires --mbps.")
            od_dict = {}
            for h in hosts:
                if h != all_to_host:
                    od_dict.setdefault(h, {})[all_to_host] = mbps
        else:
            raise typer.BadParameter(
                "od mode requires one of: --od-json, --mesh-mbps, or --all-to-host with --mbps."
            )

        gen = ODFLowGenerator(lab_name=net_env.lab.name)

        if background:
            labels = gen.start_traffic_background(
                od_dicts=od_dict,
                interval=interval,
                unit=unit_lit,
                udp=udp,
                server_args=server_args,
                client_args=client_args,
            )
            typer.echo(json.dumps({"started": labels}, indent=2))
            return

        async def _run() -> list[Any]:
            return await gen.astart_generate_traffic(
                od_dicts=od_dict,
                interval=interval,
                unit=unit_lit,
                udp=udp,
                server_args=server_args,
                client_args=client_args,
            )

        results = asyncio.run(_run())
        typer.echo(json.dumps(results, indent=2))
        return
