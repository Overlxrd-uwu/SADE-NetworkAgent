import ipaddress
import random
from typing import Optional

from pydantic import BaseModel, Field

from nika.generator.fault.injector_service import FaultInjectorService
from nika.net_env.net_env_pool import get_net_env_instance
from nika.orchestrator.problems.problem_base import ProblemMeta, RootCauseCategory, TaskDescription, TaskLevel
from nika.orchestrator.tasks.detection import DetectionTask
from nika.orchestrator.tasks.localization import LocalizationTask
from nika.orchestrator.tasks.rca import RCATask
from nika.service.kathara import KatharaBaseAPI
from nika.utils.logger import system_logger

# ==================================================================
# Problem: DHCP missing subnet
# ==================================================================


class DHCPMissingSubnetParams(BaseModel):
    """Parameters for injecting a DHCP missing subnet fault."""

    host_name: Optional[str] = Field(default=None, description="DHCP server host name. Defaults to runtime selection.")
    host_name_2: Optional[str] = Field(default=None, description="Affected client host name. Defaults to runtime selection.")


class DHCPMissingSubnetBase:
    root_cause_category: RootCauseCategory = RootCauseCategory.MISCONFIGURATION
    root_cause_name: str = "dhcp_missing_subnet"

    TAGS: str = ["dhcp"]

    Params = DHCPMissingSubnetParams

    def __init__(self, scenario_name: str | None, **kwargs):
        super().__init__()
        self.net_env = get_net_env_instance(scenario_name, **kwargs)
        self.kathara_api = KatharaBaseAPI(lab_name=self.net_env.lab.name)
        self.injector = FaultInjectorService(lab_name=self.net_env.lab.name)
        self.faulty_devices = [random.choice(self.net_env.servers["dhcp"])]
        self.faulty_devices.append(random.choice(self.net_env.hosts))

    def inject_fault(self, params: DHCPMissingSubnetParams | None = None):
        if params is None:
            params = DHCPMissingSubnetParams()
        dhcp_server = params.host_name if params.host_name is not None else self.faulty_devices[0]
        client_host = params.host_name_2 if params.host_name_2 is not None else self.faulty_devices[1]
        system_logger.info(f"Injecting DHCP missing subnet fault: DHCP server {dhcp_server}, affected host {client_host}")
        subnet = str(
            ipaddress.ip_network(
                self.kathara_api.get_host_ip(client_host, with_prefix=True), strict=False
            ).network_address
        )
        self.injector.inject_delete_subnet(dhcp_server=dhcp_server, subnet=subnet)


class DHCPMissingSubnetDetection(DHCPMissingSubnetBase, DetectionTask):
    META = ProblemMeta(
        root_cause_category=DHCPMissingSubnetBase.root_cause_category,
        root_cause_name=DHCPMissingSubnetBase.root_cause_name,
        task_level=TaskLevel.DETECTION,
        description=TaskDescription.DETECTION,
    )


class DHCPMissingSubnetLocalization(DHCPMissingSubnetBase, LocalizationTask):
    META = ProblemMeta(
        root_cause_category=DHCPMissingSubnetBase.root_cause_category,
        root_cause_name=DHCPMissingSubnetBase.root_cause_name,
        task_level=TaskLevel.LOCALIZATION,
        description=TaskDescription.LOCALIZATION,
    )


class DHCPMissingSubnetRCA(DHCPMissingSubnetBase, RCATask):
    META = ProblemMeta(
        root_cause_category=DHCPMissingSubnetBase.root_cause_category,
        root_cause_name=DHCPMissingSubnetBase.root_cause_name,
        task_level=TaskLevel.RCA,
        description=TaskDescription.RCA,
    )


if __name__ == "__main__":
    problem = DHCPMissingSubnetRCA(scenario_name="ospf_enterprise_dhcp")
    # problem.inject_fault()
