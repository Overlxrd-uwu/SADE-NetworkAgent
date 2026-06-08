import logging
import random
from typing import Optional

from pydantic import BaseModel, Field

from nika.generator.fault.injector_service import FaultInjectorService
from nika.net_env.base import NetworkEnvBase
from nika.net_env.net_env_pool import get_net_env_instance
from nika.orchestrator.problems.problem_base import ProblemMeta, RootCauseCategory, TaskDescription, TaskLevel
from nika.orchestrator.tasks.detection import DetectionTask
from nika.orchestrator.tasks.localization import LocalizationTask
from nika.orchestrator.tasks.rca import RCATask
from nika.service.kathara import KatharaAPIALL
from nika.utils.logger import system_logger

# ==================================================================
# Problem: Web service under DoS attack
# ==================================================================


class WebDoSParams(BaseModel):
    """Parameters for injecting a web DoS attack fault."""

    host_name: Optional[str] = Field(default=None, description="Target web server host name. Defaults to runtime selection.")
    attacker_device: Optional[str] = Field(default=None, description="Attacker host name. Defaults to the last host.")


class WebDoSBase:
    root_cause_category: RootCauseCategory = RootCauseCategory.NETWORK_UNDER_ATTACK
    root_cause_name: str = "web_dos_attack"
    symptom_desc: str = "Users reports high latency when accessing some web services."
    TAGS: str = ["http"]

    Params = WebDoSParams

    def __init__(self, scenario_name: NetworkEnvBase, **kwargs):
        super().__init__()
        self.logger = system_logger
        self.net_env = get_net_env_instance(scenario_name, **kwargs)
        self.kathara_api = KatharaAPIALL(lab_name=self.net_env.lab.name)
        self.injector = FaultInjectorService(lab_name=self.net_env.lab.name)
        self.faulty_devices = [random.choice(self.net_env.servers["web"])]
        self.attacker_device = self.net_env.hosts[-1]
        self.target_website = self.kathara_api.get_host_ip(self.faulty_devices[0], with_prefix=False)

    def inject_fault(self, params: WebDoSParams | None = None):
        if params is None:
            params = WebDoSParams()
        web_server = params.host_name if params.host_name is not None else self.faulty_devices[0]
        attacker = params.attacker_device if params.attacker_device is not None else self.attacker_device
        target_ip = self.kathara_api.get_host_ip(web_server, with_prefix=False)
        self.injector.inject_ab_attack(attacker_host=attacker, website=target_ip)


class WebDoSDetection(WebDoSBase, DetectionTask):
    META = ProblemMeta(
        root_cause_category=WebDoSBase.root_cause_category,
        root_cause_name=WebDoSBase.root_cause_name,
        task_level=TaskLevel.DETECTION,
        description=TaskDescription.DETECTION,
    )


class WebDoSLocalization(WebDoSBase, LocalizationTask):
    META = ProblemMeta(
        root_cause_category=WebDoSBase.root_cause_category,
        root_cause_name=WebDoSBase.root_cause_name,
        task_level=TaskLevel.LOCALIZATION,
        description=TaskDescription.LOCALIZATION,
    )


class WebDoSRCA(WebDoSBase, RCATask):
    META = ProblemMeta(
        root_cause_category=WebDoSBase.root_cause_category,
        root_cause_name=WebDoSBase.root_cause_name,
        task_level=TaskLevel.RCA,
        description=TaskDescription.RCA,
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    problem = WebDoSBase(scenario_name="dc_clos_service")
    # problem.inject_fault()
