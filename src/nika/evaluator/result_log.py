import csv
import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from nika.config import RESULTS_DIR
from nika.evaluator.llm_judge import JudgeResponse
from nika.evaluator.trace_parser import AgentTraceParser
from nika.orchestrator.problems.prob_pool import get_problem_instance

load_dotenv()

EVAL_METRICS_FILENAME = "eval_metrics.json"
RUN_FILENAME = "run.json"
GROUND_TRUTH_FILENAME = "ground_truth.json"
SUBMISSION_FILENAME = "submission.json"
LLM_JUDGE_FILENAME = "llm_judge.json"
MESSAGES_FILENAME = "messages.jsonl"

SUMMARY_REQUIRED_ARTIFACTS = (RUN_FILENAME, GROUND_TRUTH_FILENAME, EVAL_METRICS_FILENAME)


@dataclass
class EvalResult:
    agent_type: str = None
    model: str = None
    root_cause_category: str = None
    root_cause_name: str = None
    net_env: str = None
    scenario_topo_size: str = None
    session_id: str = None
    in_tokens: int = None
    out_tokens: int = None
    steps: int = None
    tool_calls: int = None
    tool_errors: int = None
    time_taken: float = None
    llm_judge_relevance_score: int = None
    llm_judge_correctness_score: int = None
    llm_judge_efficiency_score: int = None
    llm_judge_clarity_score: int = None
    llm_judge_final_outcome_score: int = None
    llm_judge_overall_score: int = None
    detection_score: float = None
    localization_accuracy: float = None
    localization_precision: float = None
    localization_recall: float = None
    localization_f1: float = None
    rca_accuracy: float = None
    rca_precision: float = None
    rca_recall: float = None
    rca_f1: float = None


def _session_duration_seconds(start_time, end_time) -> float | None:
    if start_time is None or end_time is None:
        return None
    try:
        return round(float(end_time) - float(start_time), 2)
    except (TypeError, ValueError):
        start_dt = datetime.fromisoformat(str(start_time))
        end_dt = datetime.fromisoformat(str(end_time))
        return round((end_dt - start_dt).total_seconds(), 2)


def default_summary_csv_path() -> str:
    return os.path.join(RESULTS_DIR, "0_summary", "evaluation_summary.csv")


def missing_summary_artifacts(session_dir: Path) -> list[str]:
    return [name for name in SUMMARY_REQUIRED_ARTIFACTS if not (session_dir / name).exists()]


def is_finished_session(run_meta: dict) -> bool:
    if run_meta.get("status") == "finished":
        return True
    return run_meta.get("end_time") is not None


def iter_session_dirs(results_dir: str | Path | None = None) -> list[Path]:
    root = Path(results_dir or RESULTS_DIR)
    if not root.exists():
        return []
    session_dirs: list[Path] = []
    for entry in sorted(root.iterdir()):
        if not entry.is_dir() or entry.name == "0_summary":
            continue
        if (entry / RUN_FILENAME).exists():
            session_dirs.append(entry)
    return session_dirs


def resolve_root_cause_category(run_meta: dict) -> str | None:
    category = run_meta.get("root_cause_category")
    if category:
        return str(category)
    problem_names = run_meta.get("problem_names") or []
    if not problem_names:
        return None
    try:
        problem = get_problem_instance(
            problem_names=problem_names,
            task_level="detection",
            scenario_name=run_meta.get("scenario_name", ""),
            **(run_meta.get("scenario_params") or {}),
        )
        return str(problem.root_cause_category)
    except Exception:
        return None


def build_eval_result_from_session_dir(session_dir: Path) -> EvalResult:
    missing = missing_summary_artifacts(session_dir)
    if missing:
        raise FileNotFoundError(
            f"Session directory {session_dir} is missing artifacts required for summary CSV: {', '.join(missing)}"
        )

    run_meta = json.loads((session_dir / RUN_FILENAME).read_text(encoding="utf-8"))
    if not is_finished_session(run_meta):
        raise ValueError(f"Session {run_meta.get('session_id', session_dir.name)} is not finished.")

    metrics_blob = json.loads((session_dir / EVAL_METRICS_FILENAME).read_text(encoding="utf-8"))

    judge_response: JudgeResponse | None = None
    judge_path = session_dir / LLM_JUDGE_FILENAME
    if judge_path.exists():
        judge_response = JudgeResponse.model_validate_json(judge_path.read_text(encoding="utf-8"))

    trace_metrics = {
        "in_tokens": metrics_blob.get("in_tokens"),
        "out_tokens": metrics_blob.get("out_tokens"),
        "steps": metrics_blob.get("steps"),
        "tool_calls": metrics_blob.get("tool_calls"),
        "tool_errors": metrics_blob.get("tool_errors"),
    }
    if not any(v is not None for v in trace_metrics.values()):
        trace_path = session_dir / MESSAGES_FILENAME
        if trace_path.exists():
            trace_metrics = AgentTraceParser(trace_path=str(trace_path)).parse_trace()

    if judge_response:
        relevance_score = judge_response.scores.relevance.score
        correctness_score = judge_response.scores.correctness.score
        efficiency_score = judge_response.scores.efficiency.score
        clarity_score = judge_response.scores.clarity.score
        final_outcome_score = judge_response.scores.final_outcome.score
        overall_score = judge_response.scores.overall_score.score
    else:
        relevance_score = correctness_score = efficiency_score = clarity_score = None
        final_outcome_score = overall_score = None

    return EvalResult(
        agent_type=run_meta.get("agent_type"),
        model=run_meta.get("model"),
        root_cause_category=resolve_root_cause_category(run_meta),
        root_cause_name=run_meta.get("root_cause_name"),
        net_env=run_meta.get("scenario_name"),
        scenario_topo_size=run_meta.get("scenario_topo_size"),
        session_id=run_meta.get("session_id") or session_dir.name,
        in_tokens=trace_metrics.get("in_tokens"),
        out_tokens=trace_metrics.get("out_tokens"),
        steps=trace_metrics.get("steps"),
        tool_calls=trace_metrics.get("tool_calls"),
        tool_errors=trace_metrics.get("tool_errors"),
        time_taken=_session_duration_seconds(run_meta.get("start_time"), run_meta.get("end_time")),
        llm_judge_relevance_score=relevance_score,
        llm_judge_correctness_score=correctness_score,
        llm_judge_efficiency_score=efficiency_score,
        llm_judge_clarity_score=clarity_score,
        llm_judge_final_outcome_score=final_outcome_score,
        llm_judge_overall_score=overall_score,
        detection_score=metrics_blob.get("detection_score", -1.0),
        localization_accuracy=metrics_blob.get("localization_accuracy", -1.0),
        localization_precision=metrics_blob.get("localization_precision", -1.0),
        localization_recall=metrics_blob.get("localization_recall", -1.0),
        localization_f1=metrics_blob.get("localization_f1", -1.0),
        rca_accuracy=metrics_blob.get("rca_accuracy", -1.0),
        rca_precision=metrics_blob.get("rca_precision", -1.0),
        rca_recall=metrics_blob.get("rca_recall", -1.0),
        rca_f1=metrics_blob.get("rca_f1", -1.0),
    )


def write_eval_summary_csv(eval_results: list[EvalResult], output_path: str | Path) -> Path:
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(asdict(EvalResult()).keys())
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for result in eval_results:
            writer.writerow(asdict(result))
    return out
