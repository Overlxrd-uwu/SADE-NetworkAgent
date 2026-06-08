import logging
import random
from typing import Optional

from pydantic import BaseModel, Field

from nika.generator.fault.injector_host import FaultInjectorHost
from nika.net_env.net_env_pool import get_net_env_instance
from nika.orchestrator.problems.problem_base import ProblemMeta, RootCauseCategory, TaskDescription, TaskLevel
from nika.orchestrator.tasks.detection import DetectionTask
from nika.orchestrator.tasks.localization import LocalizationTask
from nika.orchestrator.tasks.rca import RCATask
from nika.service.kathara import KatharaAPIALL
from nika.utils.logger import system_logger

# ==================================================================
# Problem: MAC address conflict
# ==================================================================


class MacAddressConflictParams(BaseModel):
    """Parameters for injecting a MAC address conflict fault."""

    host_name: Optional[str] = Field(default=None, description="Target host/device receiving conflicting MAC. Defaults to runtime selection.")
    host_name_2: Optional[str] = Field(default=None, description="Peer device whose MAC is copied. Defaults to runtime selection.")


class MacAddressConflictBase:
    root_cause_category: RootCauseCategory = RootCauseCategory.MISCONFIGURATION
    root_cause_name: str = "mac_address_conflict"
    TAGS: str = ["mac"]

    Params = MacAddressConflictParams

    def __init__(self, scenario_name: str | None, **kwargs):
        super().__init__()
        self.logger = system_logger

        self.net_env = get_net_env_instance(scenario_name, **kwargs)
        self.kathara_api = KatharaAPIALL(lab_name=self.net_env.lab.name)
        self.injector = FaultInjectorHost(lab_name=self.net_env.lab.name)
        topo = self.net_env.get_topology()
        faulty_link = random.choice(topo)
        device_1, device_2 = faulty_link
        device_1, intf_1 = device_1.split(":")
        device_2, intf_2 = device_2.split(":")
        self.faulty_devices = [device_1, device_2]
        self.falty_links = [intf_1, intf_2]

    def inject_fault(self, params: MacAddressConflictParams | None = None):
        if params is None:
            params = MacAddressConflictParams()
        device_0 = params.host_name if params.host_name is not None else self.faulty_devices[0]
        device_1 = params.host_name_2 if params.host_name_2 is not None else self.faulty_devices[1]
        target_mac = self.kathara_api.get_host_mac_address(device_1, self.falty_links[1])
        self.kathara_api.exec_cmd(host_name=device_0, command=f"ip link set dev eth0 address {target_mac}")
        self.logger.info(f"Injected MAC address conflict on {device_0} with MAC {target_mac} of {device_1}")


class MacAddressConflictDetection(MacAddressConflictBase, DetectionTask):
    META = ProblemMeta(
        root_cause_category=MacAddressConflictBase.root_cause_category,
        root_cause_name=MacAddressConflictBase.root_cause_name,
        task_level=TaskLevel.DETECTION,
        description=TaskDescription.DETECTION,
    )


class MacAddressConflictLocalization(MacAddressConflictBase, LocalizationTask):
    META = ProblemMeta(
        root_cause_category=MacAddressConflictBase.root_cause_category,
        root_cause_name=MacAddressConflictBase.root_cause_name,
        task_level=TaskLevel.LOCALIZATION,
        description=TaskDescription.LOCALIZATION,
    )


class MacAddressConflictRCA(MacAddressConflictBase, RCATask):
    META = ProblemMeta(
        root_cause_category=MacAddressConflictBase.root_cause_category,
        root_cause_name=MacAddressConflictBase.root_cause_name,
        task_level=TaskLevel.RCA,
        description=TaskDescription.RCA,
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    problem = MacAddressConflictBase(scenario_name="ospf_enterprise_static", topo_size="s")
    # problem.inject_fault()
