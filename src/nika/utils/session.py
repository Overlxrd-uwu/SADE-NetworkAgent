import json
import os
from datetime import datetime
from typing import Any

from nika.config import RESULTS_DIR
from nika.utils.session_store import SessionStore


class Session:
    def __init__(self) -> None:
        self.store = SessionStore()

    def init_session(
        self,
        *,
        session_id: str,
        scenario_name: str,
        lab_name: str,
        scenario_topo_size: str | None,
        scenario_params: dict | None = None,
    ) -> None:
        self.session_id = session_id
        self.scenario_name = scenario_name
        self.lab_name = lab_name
        self.scenario_topo_size = scenario_topo_size
        self.scenario_params = scenario_params or {}
        self.store.create_session(
            {
                "session_id": self.session_id,
                "lab_name": self.lab_name,
                "scenario_name": self.scenario_name,
                "scenario_topo_size": self.scenario_topo_size,
                "scenario_params": self.scenario_params,
                "status": "running",
            }
        )

    def load_running_session(self, session_id: str | None = None):
        session_meta = (
            self.store.get_session(session_id)
            if session_id is not None
            else self.store.get_unique_running_session()
        )
        if session_meta.get("status") != "running":
            raise ValueError(f"Session '{session_meta.get('session_id')}' is not running.")
        for key, value in session_meta.items():
            setattr(self, key, value)
        return self

    def _write_session(self) -> str:
        if not hasattr(self, "session_id"):
            raise ValueError("Session ID is not set.")
        payload = {k: v for k, v in self.__dict__.items() if k != "store"}
        self.store.update_session(self.session_id, payload)
        if getattr(self, "session_dir", None):
            self._write_run_json(payload)
        return self.session_id

    def _write_run_json(self, payload: dict) -> None:
        """Write/update run.json in the session results directory."""
        os.makedirs(self.session_dir, exist_ok=True)
        run_path = os.path.join(self.session_dir, "run.json")
        serializable = {k: v for k, v in payload.items() if k not in ("store", "failure_injections")}
        with open(run_path, "w", encoding="utf-8") as f:
            json.dump(serializable, f, indent=2, default=str)

    def update_session(self, key: str, value: Any):
        setattr(self, key, value)
        if hasattr(self, "problem_names") and hasattr(self, "session_id"):
            if len(self.problem_names) > 1:
                self.root_cause_name = "multiple_faults"
            else:
                self.root_cause_name = self.problem_names[0]
            self.session_dir = f"{RESULTS_DIR}/{self.root_cause_name}/{self.session_id}"
        self._write_session()

    def write_gt(self, gt: dict[str, Any]):
        os.makedirs(self.session_dir, exist_ok=True)
        with open(self.session_dir + "/ground_truth.json", "w") as f:
            f.write(json.dumps(gt, indent=4))

    def clear_session(self):
        if not hasattr(self, "session_id"):
            raise ValueError("Session ID is not set.")
        payload = {k: v for k, v in self.__dict__.items() if k != "store"}
        payload["status"] = "finished"
        if getattr(self, "session_dir", None):
            self._write_run_json(payload)
        self.store.delete_session(self.session_id)

    def start_session(self):
        self.start_time = datetime.now().isoformat()
        self._write_session()

    def end_session(self):
        self.end_time = datetime.now().isoformat()
        self._write_session()

    def __str__(self) -> str:
        payload = {k: v for k, v in self.__dict__.items() if k != "store"}
        return str(payload)
