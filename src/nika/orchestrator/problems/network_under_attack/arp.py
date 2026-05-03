import random

from nika.generator.fault.injector_host import FaultInjectorHost
from nika.net_env.net_env_pool import get_net_env_instance
from nika.orchestrator.problems.problem_base import ProblemMeta, RootCauseCategory, TaskDescription, TaskLevel
from nika.orchestrator.tasks.detection import DetectionTask
from nika.orchestrator.tasks.localization import LocalizationTask
from nika.orchestrator.tasks.rca import RCATask
from nika.service.kathara import KatharaAPIALL
from nika.utils.logger import system_logger

# ==================================================================
# Problem: Arp cache poisoning causing data plane issues.
# ==================================================================


class ArpCachePoisoningBase:
    root_cause_category: RootCauseCategory = RootCauseCategory.NETWORK_UNDER_ATTACK
    root_cause_name: str = "arp_cache_poisoning"
    TAGS: str = ["arp"]

    def __init__(self, scenario_name: str | None, **kwargs):
        super().__init__()
        self.logger = system_logger
        self.net_env = get_net_env_instance(scenario_name, **kwargs)
        self.kathara_api = KatharaAPIALL(lab_name=self.net_env.lab.name)
        self.injector = FaultInjectorHost(lab_name=self.net_env.lab.name)
        self.faulty_devices = [random.choice(self.net_env.hosts)]

    def inject_fault(self):
        default_gateway = self.kathara_api.get_default_gateway(self.faulty_devices[0])
        self.injector.inject_arp_misconfiguration(
            host_name=self.faulty_devices[0],
            ip_address=default_gateway,
            fake_mac="00:11:22:33:44:55",
        )

    def recover_fault(self):
        default_gateway = self.kathara_api.get_default_gateway(self.faulty_devices[0])
        self.injector.recover_arp_misconfiguration(
            host_name=self.faulty_devices[0],
            ip_address=default_gateway,
        )


class ArpCachePoisoningDetection(ArpCachePoisoningBase, DetectionTask):
    META = ProblemMeta(
        root_cause_category=ArpCachePoisoningBase.root_cause_category,
        root_cause_name=ArpCachePoisoningBase.root_cause_name,
        task_level=TaskLevel.DETECTION,
        description=TaskDescription.DETECTION,
    )


class ArpCachePoisoningLocalization(ArpCachePoisoningBase, LocalizationTask):
    META = ProblemMeta(
        root_cause_category=ArpCachePoisoningBase.root_cause_category,
        root_cause_name=ArpCachePoisoningBase.root_cause_name,
        task_level=TaskLevel.LOCALIZATION,
        description=TaskDescription.LOCALIZATION,
    )


class ArpCachePoisoningRCA(ArpCachePoisoningBase, RCATask):
    META = ProblemMeta(
        root_cause_category=ArpCachePoisoningBase.root_cause_category,
        root_cause_name=ArpCachePoisoningBase.root_cause_name,
        task_level=TaskLevel.RCA,
        description=TaskDescription.RCA,
    )
