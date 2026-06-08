import random
from typing import Optional

from pydantic import BaseModel, Field

from nika.generator.fault.injector_base import FaultInjectorBase
from nika.net_env.net_env_pool import get_net_env_instance
from nika.orchestrator.problems.problem_base import ProblemMeta, RootCauseCategory, TaskDescription, TaskLevel
from nika.orchestrator.tasks.detection import DetectionTask
from nika.orchestrator.tasks.localization import LocalizationTask
from nika.orchestrator.tasks.rca import RCATask
from nika.service.kathara import KatharaAPIALL
from nika.utils.logger import system_logger

logger = system_logger


# ==================================================================
# Problem: P4 aggressive detection thresholds of Bloom filter
# ==================================================================


class P4AggressiveDetectionThresholdsParams(BaseModel):
    """Parameters for injecting a P4 aggressive detection thresholds fault."""

    host_name: Optional[str] = Field(default=None, description="Target BMv2 switch name. Defaults to a randomly selected switch.")
    p4_name: Optional[str] = Field(default=None, description="P4 program name (without suffix). Defaults to runtime detection.")


class P4AggressiveDetectionThresholdsBase:
    root_cause_category = RootCauseCategory.NETWORK_NODE_ERROR
    root_cause_name = "p4_aggressive_detection_thresholds"
    TAGS: str = ["p4", "bloom_filter"]

    Params = P4AggressiveDetectionThresholdsParams

    def __init__(self, scenario_name: str | None, **kwargs):
        super().__init__()
        self.net_env = get_net_env_instance(scenario_name, **kwargs)
        self.kathara_api = KatharaAPIALL(lab_name=self.net_env.lab.name)
        self.injector = FaultInjectorBase(lab_name=self.net_env.lab.name)
        self.faulty_devices = [random.choice(self.net_env.bmv2_switches)]

    def inject_fault(self, params: P4AggressiveDetectionThresholdsParams | None = None):
        if params is None:
            params = P4AggressiveDetectionThresholdsParams()
        host = params.host_name if params.host_name is not None else self.faulty_devices[0]
        p4_name = params.p4_name if params.p4_name is not None else getattr(self, "p4_name", None)
        if p4_name is None:
            p4_name = self.kathara_api.exec_cmd(host, "echo *.p4 | sed 's/\\.p4//'").strip()
        self.kathara_api.exec_cmd(
            host,
            f"cp {p4_name}.p4 {p4_name}.p4.bak && "
            f"rm {p4_name}.json && "
            f"sed -Ei 's/#define PACKET_THRESHOLD 1000/#define PACKET_THRESHOLD 100/g' {p4_name}.p4 ",
        )
        self.kathara_api.exec_cmd(host, "pkill -f simple_switch")
        self.kathara_api.exec_cmd(host, f"./hostlab/{host}.startup")


class P4AggressiveDetectionThresholdsDetection(P4AggressiveDetectionThresholdsBase, DetectionTask):
    META = ProblemMeta(
        root_cause_category=P4AggressiveDetectionThresholdsBase.root_cause_category,
        root_cause_name=P4AggressiveDetectionThresholdsBase.root_cause_name,
        task_level=TaskLevel.DETECTION,
        description=TaskDescription.DETECTION,
    )


class P4AggressiveDetectionThresholdsLocalization(P4AggressiveDetectionThresholdsBase, LocalizationTask):
    META = ProblemMeta(
        root_cause_category=P4AggressiveDetectionThresholdsBase.root_cause_category,
        root_cause_name=P4AggressiveDetectionThresholdsBase.root_cause_name,
        task_level=TaskLevel.LOCALIZATION,
        description=TaskDescription.LOCALIZATION,
    )


class P4AggressiveDetectionThresholdsRCA(P4AggressiveDetectionThresholdsBase, RCATask):
    META = ProblemMeta(
        root_cause_category=P4AggressiveDetectionThresholdsBase.root_cause_category,
        root_cause_name=P4AggressiveDetectionThresholdsBase.root_cause_name,
        task_level=TaskLevel.RCA,
        description=TaskDescription.RCA,
    )
