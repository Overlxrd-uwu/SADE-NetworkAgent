"""Inject configured faults for the current session and write ground truth."""

import json
import random
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import ValidationError

from nika.orchestrator.problems.prob_pool import get_problem_instance, list_avail_problem_names
from nika.orchestrator.problems.problem_base import TaskLevel
from nika.utils.failure_params import get_failure_param_schema, resolve_failure_params
from nika.utils.logger import bind_session_dir, log_event
from nika.utils.session import Session
from nika.utils.session_store import SessionStore


def _json_safe(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    return str(value)


def _extract_injection_params(problem: Any) -> dict[str, Any]:
    params: dict[str, Any] = {"problem_class": problem.__class__.__name__}
    for attr in (
        "faulty_devices",
        "faulty_intf",
        "intf_name",
        "service_name",
        "attacker_device",
        "target_host",
        "target_website",
        "target_domain",
        "p4_name",
        "southbound_port",
        "original_port",
        "mismatched_port",
    ):
        if hasattr(problem, attr):
            params[attr] = _json_safe(getattr(problem, attr))
    return params


def _default_param_context(problem: Any) -> dict[str, Any]:
    context: dict[str, Any] = {}
    faulty_devices = getattr(problem, "faulty_devices", None)
    if isinstance(faulty_devices, list) and faulty_devices:
        context["host_name"] = faulty_devices[0]
    elif isinstance(faulty_devices, str):
        context["host_name"] = faulty_devices
    if hasattr(problem, "faulty_intf"):
        context["intf_name"] = getattr(problem, "faulty_intf")
    elif hasattr(problem, "intf_name"):
        context["intf_name"] = getattr(problem, "intf_name")
    return context


def _apply_param_overrides(problem: Any, params: dict[str, Any]) -> None:
    if not params:
        return
    faulty_devices = getattr(problem, "faulty_devices", None)
    if "host_name" in params:
        host_name = params["host_name"]
        if isinstance(faulty_devices, list) and faulty_devices:
            faulty_devices[0] = host_name
        elif isinstance(faulty_devices, str):
            setattr(problem, "faulty_devices", [host_name])
        else:
            setattr(problem, "faulty_devices", [host_name])

    for idx in range(1, 5):
        key = f"host_name_{idx}"
        if key in params:
            host_name = params[key]
            if not isinstance(faulty_devices, list):
                faulty_devices = []
            while len(faulty_devices) < idx:
                faulty_devices.append(host_name)
            faulty_devices[idx - 1] = host_name
            setattr(problem, "faulty_devices", faulty_devices)

    if "intf_name" in params:
        if hasattr(problem, "faulty_intf"):
            setattr(problem, "faulty_intf", params["intf_name"])
        if hasattr(problem, "intf_name"):
            setattr(problem, "intf_name", params["intf_name"])

    for key, value in params.items():
        if key in {"host_name", "intf_name"} or key.startswith("host_name_"):
            continue
        setattr(problem, key, value)


def inject_failure(
    problem_names: list[str],
    *,
    re_inject: bool = True,
    session_id: str | None = None,
    param_overrides: dict[str, str] | None = None,
) -> None:
    """Inject faults for ``problem_names`` into the lab for the running session."""
    session = Session()
    session.load_running_session(session_id=session_id)
    session.update_session("problem_names", problem_names)

    # Bind per-session event logging now that session_dir is set.
    bind_session_dir(session.session_dir)

    store = SessionStore()

    for problem_name in problem_names:
        if problem_name not in list_avail_problem_names():
            raise ValueError(f"Unknown problem name: {problem_name}")

    scenario_params = session.scenario_params if hasattr(session, "scenario_params") else {}
    overrides = dict(param_overrides or {})
    if overrides and len(problem_names) != 1:
        raise ValueError("When using --set parameters, inject exactly one problem at a time.")

    tot_tasks = []
    for task_level in TaskLevel:
        random.seed(session.session_id[-4:])
        problem = get_problem_instance(
            problem_names=problem_names,
            task_level=task_level,
            scenario_name=session.scenario_name,
            **scenario_params,
        )
        tot_tasks.append(problem)

    inject_meta = getattr(tot_tasks[0], "META", None)
    if inject_meta is not None:
        category = str(getattr(inject_meta, "root_cause_category", ""))
        if category:
            session.update_session("root_cause_category", category)

    failure_rows: list[tuple[int, str]] = []
    if re_inject:
        inject_problem = tot_tasks[0]
        now_ts = datetime.now().timestamp()
        effective_params: dict[str, Any] = {}
        if len(problem_names) == 1:
            effective_params = resolve_failure_params(
                problem_names[0],
                overrides,
                context=_default_param_context(inject_problem),
            )

        if len(problem_names) > 1 and hasattr(inject_problem, "sub_faults"):
            sub_faults = list(getattr(inject_problem, "sub_faults"))
            for idx, problem_name in enumerate(problem_names):
                sub_problem = sub_faults[idx] if idx < len(sub_faults) else inject_problem
                failure_id = store.create_failure_injection(
                    {
                        "session_id": session.session_id,
                        "problem_name": problem_name,
                        "root_cause_category": str(
                            getattr(getattr(sub_problem, "META", None), "root_cause_category", "")
                        ),
                        "scenario_name": session.scenario_name,
                        "lab_name": session.lab_name,
                        "injection_params": _extract_injection_params(sub_problem),
                        "status": "pending",
                        "start_time": now_ts,
                    }
                )
                failure_rows.append((failure_id, problem_name))
        else:
            params_snapshot = _extract_injection_params(inject_problem)
            if effective_params:
                params_snapshot["resolved_params"] = _json_safe(effective_params)
            if overrides:
                params_snapshot["requested_overrides"] = _json_safe(overrides)
            schema = get_failure_param_schema(problem_names[0])
            if schema is not None:
                params_snapshot["param_schema"] = schema.problem_name
            failure_id = store.create_failure_injection(
                {
                    "session_id": session.session_id,
                    "problem_name": problem_names[0],
                    "root_cause_category": str(getattr(getattr(inject_problem, "META", None), "root_cause_category", "")),
                    "scenario_name": session.scenario_name,
                    "lab_name": session.lab_name,
                    "injection_params": params_snapshot,
                    "status": "pending",
                    "start_time": now_ts,
                }
            )
            failure_rows.append((failure_id, problem_names[0]))

        ParamsClass = getattr(type(inject_problem), "Params", None)
        if ParamsClass is not None:
            # Pydantic-aware failure: build and validate the params model, then pass it in.
            try:
                fault_params = ParamsClass(**overrides) if overrides else ParamsClass()
            except ValidationError as exc:
                raise ValueError(f"Invalid parameters for '{problem_names[0]}': {exc}") from exc
            inject_problem.inject_fault(params=fault_params)
        else:
            # Legacy path: apply overrides via attribute assignment.
            if len(problem_names) == 1 and effective_params:
                _apply_param_overrides(inject_problem, effective_params)
            inject_problem.inject_fault()
        for failure_id, problem_name in failure_rows:
            store.update_failure_injection(
                session.session_id,
                failure_id,
                {"status": "injected"},
            )
            log_event(
                "failure_injected",
                f"Failure injected: session={session.session_id}, problem={problem_name}",
                session_id=session.session_id,
                problem=problem_name,
            )

    log_event(
        "failure_inject_complete",
        f"Session {session.session_id}: injected {problem_names} under {session.scenario_name}.",
        session_id=session.session_id,
        problems=problem_names,
        scenario=session.scenario_name,
    )
    task_description = problem.get_task_description()
    session.update_session("task_description", task_description)

    tot_gt = {}
    for prob in tot_tasks:
        gt = prob.get_submission().model_dump_json()
        tot_gt.update(json.loads(gt))

    session.write_gt(tot_gt)
    log_event(
        "ground_truth_saved",
        f"Ground truth saved for session {session.session_id}.",
        session_id=session.session_id,
    )
