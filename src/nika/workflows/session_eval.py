"""Session evaluation: numeric metrics, LLM judge, and session teardown."""

import json
import os
import textwrap
from pathlib import Path

from nika.evaluator.llm_judge import LLMJudge
from nika.evaluator.result_log import EVAL_METRICS_FILENAME, MESSAGES_FILENAME
from nika.evaluator.trace_parser import AgentTraceParser
from nika.net_env.net_env_pool import get_net_env_instance
from nika.orchestrator.tasks.detection import DetectionSubmission
from nika.orchestrator.tasks.localization import LocalizationTask
from nika.orchestrator.tasks.rca import RCATask
from nika.utils.logger import log_event, system_logger
from nika.utils.session import Session
from nika.utils.session_store import SessionStore

logger = system_logger


def generic_eval(gt, submission):
    """Score detection, localization, and RCA from structured ``gt`` and ``submission``."""
    try:
        parsed_detect_sub = DetectionSubmission.model_validate({"is_anomaly": submission.get("is_anomaly", False)})
        if gt["is_anomaly"] == parsed_detect_sub.is_anomaly:
            detection_score = 1.0
        else:
            detection_score = 0.0
    except Exception:
        detection_score = -1.0

    try:
        loc_acc, loc_prec, loc_rec, loc_f1 = LocalizationTask().eval(
            submission={"faulty_devices": submission.get("faulty_devices", [])},
            gt={"faulty_devices": gt.get("faulty_devices", [])},
        )
    except Exception:
        loc_acc, loc_prec, loc_rec, loc_f1 = -1.0, -1.0, -1.0, -1.0

    try:
        rca_acc, rca_prec, rca_rec, rca_f1 = RCATask().eval(
            submission={"root_cause_name": submission.get("root_cause_name", [])},
            gt={"root_cause_name": gt.get("root_cause_name", [])},
        )
    except Exception:
        rca_acc, rca_prec, rca_rec, rca_f1 = -1.0, -1.0, -1.0, -1.0

    return (
        detection_score,
        loc_acc,
        loc_prec,
        loc_rec,
        loc_f1,
        rca_acc,
        rca_prec,
        rca_rec,
        rca_f1,
    )


def run_eval_metrics(*, session_id: str | None = None) -> None:
    """Compute rule-based scores and trace stats; write ``eval_metrics.json`` under the session dir."""
    session = Session()
    session.load_running_session(session_id=session_id)

    gt_path = Path(session.session_dir) / "ground_truth.json"
    gt = json.loads(gt_path.read_text())

    submission_path = Path(session.session_dir) / "submission.json"
    if submission_path.exists():
        submission = json.loads(submission_path.read_text())
        (
            detection_score,
            loc_acc,
            loc_prec,
            loc_rec,
            loc_f1,
            rca_acc,
            rca_prec,
            rca_rec,
            rca_f1,
        ) = generic_eval(gt, submission)
    else:
        logger.error(f"Submission file not found: {submission_path}")
        detection_score = -1.0
        loc_acc = loc_prec = loc_rec = loc_f1 = -1.0
        rca_acc = rca_prec = rca_rec = rca_f1 = -1.0

    trace_path = os.path.join(session.session_dir, MESSAGES_FILENAME)
    trace_metrics = AgentTraceParser(trace_path=trace_path).parse_trace()

    payload = {
        "detection_score": detection_score,
        "localization_accuracy": loc_acc,
        "localization_precision": loc_prec,
        "localization_recall": loc_rec,
        "localization_f1": loc_f1,
        "rca_accuracy": rca_acc,
        "rca_precision": rca_prec,
        "rca_recall": rca_rec,
        "rca_f1": rca_f1,
        "in_tokens": trace_metrics.get("in_tokens"),
        "out_tokens": trace_metrics.get("out_tokens"),
        "steps": trace_metrics.get("steps"),
        "tool_calls": trace_metrics.get("tool_calls"),
        "tool_errors": trace_metrics.get("tool_errors"),
    }
    out_path = Path(session.session_dir) / EVAL_METRICS_FILENAME
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    session.update_session("eval_metrics", payload)
    log_event("eval_metrics_saved", f"Wrote numeric eval metrics to {out_path}", session_id=session.session_id)


def run_llm_judge(judge_llm_backend: str, judge_model: str, *, session_id: str | None = None) -> None:
    """Run LLM-as-judge only; writes ``llm_judge.json`` under the session dir."""
    session = Session()
    session.load_running_session(session_id=session_id)

    gt_path = Path(session.session_dir) / "ground_truth.json"
    gt = json.loads(gt_path.read_text())

    trace_path = os.path.join(session.session_dir, MESSAGES_FILENAME)
    logger.info(f"Evaluating session {session.session_id} using LLM-as-Judge.")

    llm_judge = LLMJudge(judge_llm_backend=judge_llm_backend, judge_model=judge_model)
    llm_judge.evaluate_agent(
        ground_truth=textwrap.dedent(
            f"""\
                The root cause is {gt["root_cause_name"]}.
                The faulty devices are: {", ".join(gt["faulty_devices"])}.
            """
        ),
        trace_path=trace_path,
        save_path=f"{session.session_dir}/llm_judge.json",
    )
    judge_path = Path(session.session_dir) / "llm_judge.json"
    if judge_path.exists():
        session.update_session("llm_judge", json.loads(judge_path.read_text(encoding="utf-8")))


def publish_session_eval(*, destroy_env: bool = True, session_id: str | None = None) -> None:
    """Finalize a session: persist run.json, optionally undeploy, and clear runtime state."""
    session = Session()
    session.load_running_session(session_id=session_id)

    if session.end_time is None:
        session.end_session()

    log_event(
        "eval_publish",
        f"Finishing session {session.session_id} for scenario {session.scenario_name}.",
        session_id=session.session_id,
        scenario=session.scenario_name,
    )

    net_env_kwargs = {}
    if session.scenario_topo_size is not None:
        net_env_kwargs["topo_size"] = session.scenario_topo_size
    net_env = get_net_env_instance(session.scenario_name, **net_env_kwargs)
    if destroy_env and net_env.lab_exists():
        net_env.undeploy()
    log_event(
        "env_destroy",
        f"Destroyed network environment: {session.scenario_name} ({session.session_id})",
        session_id=session.session_id,
    )
    ended_cnt = SessionStore().mark_session_failures_ended(session.session_id)
    if ended_cnt:
        log_event(
            "failures_ended",
            f"Marked {ended_cnt} failure record(s) as ended",
            session_id=session.session_id,
            count=ended_cnt,
        )
    session.clear_session()


def eval_results(
    judge_llm_backend: str,
    judge_model: str,
    *,
    destroy_env: bool = True,
    session_id: str | None = None,
) -> None:
    """Run metrics, LLM judge, and finish in one call (benchmark / legacy pipeline)."""
    run_eval_metrics(session_id=session_id)
    run_llm_judge(judge_llm_backend, judge_model, session_id=session_id)
    publish_session_eval(destroy_env=destroy_env, session_id=session_id)
