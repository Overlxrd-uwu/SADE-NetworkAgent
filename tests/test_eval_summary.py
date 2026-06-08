"""Unit tests for offline eval summary CSV generation."""

import json
import tempfile
import unittest
from pathlib import Path

from nika.evaluator.result_log import (
    build_eval_result_from_session_dir,
    missing_summary_artifacts,
    write_eval_summary_csv,
)
from nika.workflows.eval_summary import run_eval_summary


class EvalSummaryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.results_dir = Path(self.temp_dir.name) / "results"
        self.session_dir = self.results_dir / "link_down" / "sid-1"
        self.session_dir.mkdir(parents=True)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _write_finished_session(self, *, with_judge: bool = False) -> None:
        (self.session_dir / "ground_truth.json").write_text(
            json.dumps(
                {
                    "is_anomaly": True,
                    "faulty_devices": ["pc1"],
                    "root_cause_name": ["link_down"],
                }
            ),
            encoding="utf-8",
        )
        (self.session_dir / "eval_metrics.json").write_text(
            json.dumps(
                {
                    "detection_score": 1.0,
                    "localization_accuracy": 1.0,
                    "localization_precision": 1.0,
                    "localization_recall": 1.0,
                    "localization_f1": 1.0,
                    "rca_accuracy": 0.0,
                    "rca_precision": 0.0,
                    "rca_recall": 0.0,
                    "rca_f1": 0.0,
                    "in_tokens": 1,
                    "out_tokens": 2,
                    "steps": 3,
                    "tool_calls": 4,
                    "tool_errors": 0,
                }
            ),
            encoding="utf-8",
        )
        (self.session_dir / "run.json").write_text(
            json.dumps(
                {
                    "session_id": "sid-1",
                    "scenario_name": "simple_bgp",
                    "root_cause_name": "link_down",
                    "root_cause_category": "link_failure",
                    "agent_type": "mock",
                    "model": "mock-v1",
                    "status": "finished",
                    "start_time": "2026-06-08T19:35:16.525289",
                    "end_time": "2026-06-08T19:35:16.526834",
                }
            ),
            encoding="utf-8",
        )
        if with_judge:
            (self.session_dir / "llm_judge.json").write_text(
                json.dumps(
                    {
                        "scores": {
                            "relevance": {"score": 4, "comment": "ok"},
                            "correctness": {"score": 4, "comment": "ok"},
                            "efficiency": {"score": 3, "comment": "ok"},
                            "clarity": {"score": 4, "comment": "ok"},
                            "final_outcome": {"score": 3, "comment": "ok"},
                            "overall_score": {"score": 4, "comment": "ok"},
                        },
                        "overall_evaluation": "good",
                        "reasoning_for_overall_score": "solid",
                    }
                ),
                encoding="utf-8",
            )

    def test_missing_summary_artifacts(self) -> None:
        self.assertEqual(missing_summary_artifacts(self.session_dir), ["run.json", "ground_truth.json", "eval_metrics.json"])

    def test_build_eval_result_from_session_dir(self) -> None:
        self._write_finished_session(with_judge=True)
        result = build_eval_result_from_session_dir(self.session_dir)
        self.assertEqual(result.session_id, "sid-1")
        self.assertEqual(result.net_env, "simple_bgp")
        self.assertEqual(result.root_cause_category, "link_failure")
        self.assertEqual(result.detection_score, 1.0)
        self.assertEqual(result.llm_judge_overall_score, 4)

    def test_run_eval_summary_filters_by_problem_and_env(self) -> None:
        self._write_finished_session()
        other_dir = self.results_dir / "host_crash" / "sid-2"
        other_dir.mkdir(parents=True)
        (other_dir / "ground_truth.json").write_text("{}", encoding="utf-8")
        (other_dir / "eval_metrics.json").write_text("{}", encoding="utf-8")
        (other_dir / "run.json").write_text(
            json.dumps(
                {
                    "session_id": "sid-2",
                    "scenario_name": "dc_clos_bgp",
                    "root_cause_name": "host_crash",
                    "status": "finished",
                    "end_time": "2026-06-08T20:00:00",
                }
            ),
            encoding="utf-8",
        )

        out_path = self.results_dir / "summary.csv"
        run_eval_summary(
            output_path=str(out_path),
            problems=["link_down"],
            envs=["simple_bgp"],
            results_dir=str(self.results_dir),
        )

        rows = list(__import__("csv").DictReader(out_path.open(encoding="utf-8")))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["session_id"], "sid-1")
        self.assertEqual(rows[0]["net_env"], "simple_bgp")

    def test_write_eval_summary_csv_overwrites_output(self) -> None:
        self._write_finished_session()
        result = build_eval_result_from_session_dir(self.session_dir)
        out_path = self.results_dir / "out.csv"
        write_eval_summary_csv([result], out_path)
        self.assertTrue(out_path.exists())
        rows = list(__import__("csv").DictReader(out_path.open(encoding="utf-8")))
        self.assertEqual(len(rows), 1)


if __name__ == "__main__":
    unittest.main()
