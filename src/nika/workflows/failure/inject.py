"""Inject configured faults for the current session and write ground truth."""

import json
import random
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import ValidationError

from nika.orchestrator.problems.prob_pool import get_problem_instance, list_avail_problem_names
from nika.orchestrator.problems.problem_base import TaskLevel
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


def inject_failure(
    problem_names: list[str],
    *,
    session_id: str | None = None,
    param_overrides: dict[str, str] | None = None,
) -> None:
    """Inject faults for ``problem_names`` into the lab for the running session."""
    session = Session()
    session.load_running_session(session_id=session_id)
    session.update_session("problem_names", problem_names)

    # Bind per-session logging now that session_dir is set.
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
    inject_problem = tot_tasks[0]
    now_ts = datetime.now().timestamp()
    ParamsClass = getattr(type(inject_problem), "Params", None)
    fault_params = None
    if ParamsClass is not None:
        try:
            fault_params = ParamsClass(**overrides) if overrides else ParamsClass()
        except ValidationError as exc:
            raise ValueError(f"Invalid parameters for '{problem_names[0]}': {exc}") from exc

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
        if fault_params is not None:
            params_snapshot["resolved_params"] = _json_safe(
                fault_params.model_dump(exclude_none=True)
            )
        if overrides:
            params_snapshot["requested_overrides"] = _json_safe(overrides)
        if ParamsClass is not None:
            params_snapshot["param_schema"] = ParamsClass.__name__
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

    if ParamsClass is not None:
        inject_problem.inject_fault(params=fault_params)
    else:
        inject_problem.inject_fault()

    if not hasattr(inject_problem, "verify_fault"):
        raise RuntimeError(f"Problem {problem_names} does not implement verify_fault")
    if fault_params is not None:
        verify_result = inject_problem.verify_fault(params=fault_params)
    else:
        verify_result = inject_problem.verify_fault()
    verify_payload = _json_safe(verify_result)
    if not verify_result.get("verified", False):
        for failure_id, _problem_name in failure_rows:
            store.update_failure_injection(
                session.session_id,
                failure_id,
                {"status": "verify_failed", "verify_result": verify_payload},
            )
        log_event(
            "failure_verify_failed",
            f"Failure verification failed: session={session.session_id}, problems={problem_names}",
            session_id=session.session_id,
            problems=problem_names,
            verify_result=verify_payload,
        )
        raise RuntimeError(
            f"Failure injection verification failed for {problem_names}: {verify_result}"
        )

    for failure_id, problem_name in failure_rows:
        store.update_failure_injection(
            session.session_id,
            failure_id,
            {"status": "injected", "verify_result": verify_payload},
        )
        log_event(
            "failure_injected",
            f"Failure injected: session={session.session_id}, problem={problem_name}",
            session_id=session.session_id,
            problem=problem_name,
        )
    log_event(
        "failure_verified",
        f"Failure verified: session={session.session_id}, problems={problem_names}",
        session_id=session.session_id,
        problems=problem_names,
        verify_result=verify_payload,
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
