import ipaddress
import logging
import random
import re
from typing import Optional

from pydantic import BaseModel, Field

from nika.generator.fault.injector_base import FaultInjectorBase
from nika.net_env.net_env_pool import get_net_env_instance
from nika.orchestrator.problems.problem_base import ProblemMeta, RootCauseCategory, TaskDescription, TaskLevel
from nika.orchestrator.tasks.detection import DetectionTask
from nika.orchestrator.tasks.localization import LocalizationTask
from nika.orchestrator.tasks.rca import RCATask
from nika.service.kathara import KatharaFRRAPI
from nika.utils.logger import system_logger

# ==================================================================
# Problem: OSPF Area Misconfiguration
# ==================================================================


class OSPFAreaMisconfigParams(BaseModel):
    """Parameters for injecting an OSPF area misconfiguration fault."""

    host_name: Optional[str] = Field(default=None, description="Target router host name. Defaults to a randomly selected router.")


class OSPFAreaMisconfigBase:
    root_cause_category: RootCauseCategory = RootCauseCategory.MISCONFIGURATION
    root_cause_name: str = "ospf_area_misconfiguration"

    TAGS: str = ["ospf"]

    Params = OSPFAreaMisconfigParams

    def __init__(self, scenario_name: str | None, **kwargs):
        super().__init__()
        self.net_env = get_net_env_instance(scenario_name, **kwargs)
        self.kathara_api = KatharaFRRAPI(lab_name=self.net_env.lab.name)
        self.injector = FaultInjectorBase(lab_name=self.net_env.lab.name)
        self.logger = system_logger
        self.faulty_devices = [random.choice(self.net_env.routers)]

    def inject_fault(self, params: OSPFAreaMisconfigParams | None = None):
        if params is None:
            params = OSPFAreaMisconfigParams()
        host = params.host_name if params.host_name is not None else self.faulty_devices[0]
        correct_area = self.kathara_api.exec_cmd(host, "vtysh -c 'show running-config'")
        pattern = re.compile(r"^\s*network\s+\S+\s+area\s+(\S+)", re.MULTILINE)
        m = pattern.search(correct_area)
        if not m:
            self.logger.error(f"Could not find OSPF area on {host}")
        correct_area = m.group(1)
        wrong_area = "66" if correct_area != "66" else "99"
        self.kathara_api.exec_cmd(
            host,
            f"vtysh -c 'show running-config' | sed -E 's/(area )({correct_area})$/\\1{wrong_area}/' > /etc/frr/frr.conf && systemctl restart frr",
        )
        self.logger.info(f"Injected OSPF area misconfiguration on {host} from area {correct_area} to {wrong_area}.")


class OSPFAreaMisconfigDetection(OSPFAreaMisconfigBase, DetectionTask):
    META = ProblemMeta(
        root_cause_category=OSPFAreaMisconfigBase.root_cause_category,
        root_cause_name=OSPFAreaMisconfigBase.root_cause_name,
        task_level=TaskLevel.DETECTION,
        description=TaskDescription.DETECTION,
    )


class OSPFAreaMisconfigLocalization(OSPFAreaMisconfigBase, LocalizationTask):
    META = ProblemMeta(
        root_cause_category=OSPFAreaMisconfigBase.root_cause_category,
        root_cause_name=OSPFAreaMisconfigBase.root_cause_name,
        task_level=TaskLevel.LOCALIZATION,
        description=TaskDescription.LOCALIZATION,
    )


class OSPFAreaMisconfigRCA(OSPFAreaMisconfigBase, RCATask):
    META = ProblemMeta(
        root_cause_category=OSPFAreaMisconfigBase.root_cause_category,
        root_cause_name=OSPFAreaMisconfigBase.root_cause_name,
        task_level=TaskLevel.RCA,
        description=TaskDescription.RCA,
    )


# ==================================================================
# Problem: OSPF Neighbor Missing
# ==================================================================


class OSPFNeighborMissingParams(BaseModel):
    """Parameters for injecting an OSPF neighbor missing fault."""

    host_name: Optional[str] = Field(default=None, description="Target router host name. Defaults to a randomly selected router.")


class OSPFNeighborMissingBase:
    root_cause_category: RootCauseCategory = RootCauseCategory.MISCONFIGURATION
    root_cause_name: str = "ospf_neighbor_missing"

    TAGS: str = ["ospf"]

    Params = OSPFNeighborMissingParams

    def __init__(self, scenario_name: str | None, **kwargs):
        super().__init__()
        self.net_env = get_net_env_instance(scenario_name, **kwargs)
        self.kathara_api = KatharaFRRAPI(lab_name=self.net_env.lab.name)
        self.injector = FaultInjectorBase(lab_name=self.net_env.lab.name)
        self.logger = system_logger
        self.faulty_devices = [random.choice(self.net_env.routers)]

    def inject_fault(self, params: OSPFNeighborMissingParams | None = None):
        if params is None:
            params = OSPFNeighborMissingParams()
        host = params.host_name if params.host_name is not None else self.faulty_devices[0]
        cmd = (
            "sed -i.bak -E "
            "'s|^([[:space:]]*)network[[:space:]]+[^[:space:]]+[[:space:]]+area|\\1# &|' "
            "/etc/frr/frr.conf"
        )
        self.kathara_api.exec_cmd(host, cmd)
        self.kathara_api.exec_cmd(host, "systemctl restart frr")
        self.logger.info(f"Injected OSPF neighbor missing on {host}.")


class OSPFNeighborMissingDetection(OSPFNeighborMissingBase, DetectionTask):
    META = ProblemMeta(
        root_cause_category=OSPFNeighborMissingBase.root_cause_category,
        root_cause_name=OSPFNeighborMissingBase.root_cause_name,
        task_level=TaskLevel.DETECTION,
        description=TaskDescription.DETECTION,
    )


class OSPFNeighborMissingLocalization(OSPFNeighborMissingBase, LocalizationTask):
    META = ProblemMeta(
        root_cause_category=OSPFNeighborMissingBase.root_cause_category,
        root_cause_name=OSPFNeighborMissingBase.root_cause_name,
        task_level=TaskLevel.LOCALIZATION,
        description=TaskDescription.LOCALIZATION,
    )


class OSPFNeighborMissingRCA(OSPFNeighborMissingBase, RCATask):
    META = ProblemMeta(
        root_cause_category=OSPFNeighborMissingBase.root_cause_category,
        root_cause_name=OSPFNeighborMissingBase.root_cause_name,
        task_level=TaskLevel.RCA,
        description=TaskDescription.RCA,
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    task = OSPFNeighborMissingBase()
    # task.inject_fault()
