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

# ==================================================================
# Problem: DHCP distributing spoofed gateway to hosts
# ==================================================================


class DHCPSpoofedGatewayParams(BaseModel):
    """Parameters for injecting a DHCP spoofed gateway fault."""

    host_name: Optional[str] = Field(default=None, description="DHCP server host name. Defaults to runtime selection.")
    host_name_2: Optional[str] = Field(default=None, description="Affected client host name. Defaults to runtime selection.")


class DHCPSpoofedGatewayBase:
    root_cause_category: RootCauseCategory = RootCauseCategory.NETWORK_UNDER_ATTACK
    root_cause_name: str = "dhcp_spoofed_gateway"

    TAGS: str = ["dhcp"]

    Params = DHCPSpoofedGatewayParams

    def __init__(self, scenario_name: str | None, **kwargs):
        super().__init__()
        self.net_env = get_net_env_instance(scenario_name, **kwargs)
        self.kathara_api = KatharaBaseAPI(lab_name=self.net_env.lab.name)
        self.injector = FaultInjectorService(lab_name=self.net_env.lab.name)
        self.faulty_devices = [random.choice(self.net_env.servers["dhcp"])]
        self.faulty_devices.append(random.choice(self.net_env.hosts))

    def inject_fault(self, params: DHCPSpoofedGatewayParams | None = None):
        if params is None:
            params = DHCPSpoofedGatewayParams()
        dhcp_server = params.host_name if params.host_name is not None else self.faulty_devices[0]
        client_host = params.host_name_2 if params.host_name_2 is not None else self.faulty_devices[1]
        subnet = str(
            ipaddress.ip_network(
                self.kathara_api.get_host_ip(client_host, with_prefix=True), strict=False
            ).network_address
        )
        self.injector.inject_wrong_gateway(
            dhcp_server=dhcp_server,
            subnet=subnet,
            wrong_gw=".".join(subnet.split(".")[:3] + ["254"]),
        )


class DHCPSpoofedGatewayDetection(DHCPSpoofedGatewayBase, DetectionTask):
    META = ProblemMeta(
        root_cause_category=DHCPSpoofedGatewayBase.root_cause_category,
        root_cause_name=DHCPSpoofedGatewayBase.root_cause_name,
        task_level=TaskLevel.DETECTION,
        description=TaskDescription.DETECTION,
    )


class DHCPSpoofedGatewayLocalization(DHCPSpoofedGatewayBase, LocalizationTask):
    META = ProblemMeta(
        root_cause_category=DHCPSpoofedGatewayBase.root_cause_category,
        root_cause_name=DHCPSpoofedGatewayBase.root_cause_name,
        task_level=TaskLevel.LOCALIZATION,
        description=TaskDescription.LOCALIZATION,
    )


class DHCPSpoofedGatewayRCA(DHCPSpoofedGatewayBase, RCATask):
    META = ProblemMeta(
        root_cause_category=DHCPSpoofedGatewayBase.root_cause_category,
        root_cause_name=DHCPSpoofedGatewayBase.root_cause_name,
        task_level=TaskLevel.RCA,
        description=TaskDescription.RCA,
    )


# ==================================================================
# Problem: DHCP distributing spoofed DNS to hosts
# ==================================================================


class DHCPSpoofedDNSParams(BaseModel):
    """Parameters for injecting a DHCP spoofed DNS fault."""

    host_name: Optional[str] = Field(default=None, description="DHCP server host name. Defaults to runtime selection.")
    host_name_2: Optional[str] = Field(default=None, description="Affected client host name. Defaults to runtime selection.")
    wrong_dns: str = Field(default="8.8.8.8", description="Spoofed DNS IP.")


class DHCPSpoofedDNSBase:
    root_cause_category: RootCauseCategory = RootCauseCategory.NETWORK_UNDER_ATTACK
    root_cause_name: str = "dhcp_spoofed_dns"

    symptom_desc = "Some hosts can not access webservices."
    TAGS: str = ["dhcp"]

    Params = DHCPSpoofedDNSParams

    def __init__(self, scenario_name: str | None, **kwargs):
        super().__init__()
        self.net_env = get_net_env_instance(scenario_name, **kwargs)
        self.kathara_api = KatharaBaseAPI(lab_name=self.net_env.lab.name)
        self.injector = FaultInjectorService(lab_name=self.net_env.lab.name)
        self.faulty_devices = [random.choice(self.net_env.servers["dhcp"])]
        self.faulty_devices.append(random.choice(self.net_env.hosts))
        self.wrong_dns = "8.8.8.8"

    def inject_fault(self, params: DHCPSpoofedDNSParams | None = None):
        if params is None:
            params = DHCPSpoofedDNSParams()
        dhcp_server = params.host_name if params.host_name is not None else self.faulty_devices[0]
        client_host = params.host_name_2 if params.host_name_2 is not None else self.faulty_devices[1]
        subnet = str(
            ipaddress.ip_network(
                self.kathara_api.get_host_ip(client_host, with_prefix=True), strict=False
            ).network_address
        )
        self.injector.inject_wrong_dns(dhcp_server=dhcp_server, subnet=subnet, wrong_dns=params.wrong_dns)


class DHCPSpoofedDNSDetection(DHCPSpoofedDNSBase, DetectionTask):
    META = ProblemMeta(
        root_cause_category=DHCPSpoofedDNSBase.root_cause_category,
        root_cause_name=DHCPSpoofedDNSBase.root_cause_name,
        task_level=TaskLevel.DETECTION,
        description=TaskDescription.DETECTION,
    )


class DHCPSpoofedDNSLocalization(DHCPSpoofedDNSBase, LocalizationTask):
    META = ProblemMeta(
        root_cause_category=DHCPSpoofedDNSBase.root_cause_category,
        root_cause_name=DHCPSpoofedDNSBase.root_cause_name,
        task_level=TaskLevel.LOCALIZATION,
        description=TaskDescription.LOCALIZATION,
    )


class DHCPSpoofedDNSRCA(DHCPSpoofedDNSBase, RCATask):
    META = ProblemMeta(
        root_cause_category=DHCPSpoofedDNSBase.root_cause_category,
        root_cause_name=DHCPSpoofedDNSBase.root_cause_name,
        task_level=TaskLevel.RCA,
        description=TaskDescription.RCA,
    )


# ==================================================================
""" Problem: DHCP missing subnet configuration """
# ==================================================================


class DHCPSpoofedSubnetParams(BaseModel):
    """Parameters for injecting a DHCP spoofed subnet fault."""

    host_name: Optional[str] = Field(default=None, description="DHCP server host name. Defaults to runtime selection.")
    host_name_2: Optional[str] = Field(default=None, description="Affected client host name. Defaults to runtime selection.")


class DHCPSpoofedSubnetBase:
    root_cause_category: RootCauseCategory = RootCauseCategory.NETWORK_UNDER_ATTACK
    root_cause_name: str = "dhcp_spoofed_subnet"

    TAGS: str = ["dhcp"]

    Params = DHCPSpoofedSubnetParams

    def __init__(self, scenario_name: str | None, **kwargs):
        super().__init__()
        self.net_env = get_net_env_instance(scenario_name, **kwargs)
        self.kathara_api = KatharaBaseAPI(lab_name=self.net_env.lab.name)
        self.injector = FaultInjectorService(lab_name=self.net_env.lab.name)
        self.faulty_devices = [random.choice(self.net_env.servers["dhcp"])]
        self.faulty_devices.append(random.choice(self.net_env.hosts))

    def inject_fault(self, params: DHCPSpoofedSubnetParams | None = None):
        if params is None:
            params = DHCPSpoofedSubnetParams()
        dhcp_server = params.host_name if params.host_name is not None else self.faulty_devices[0]
        client_host = params.host_name_2 if params.host_name_2 is not None else self.faulty_devices[1]
        subnet = str(
            ipaddress.ip_network(
                self.kathara_api.get_host_ip(client_host, with_prefix=True), strict=False
            ).network_address
        )
        self.injector.inject_delete_subnet(dhcp_server=dhcp_server, subnet=subnet)
