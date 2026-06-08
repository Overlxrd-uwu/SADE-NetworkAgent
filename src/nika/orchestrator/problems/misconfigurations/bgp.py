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
from nika.service.kathara import KatharaAPIALL

# ==================================================================
""" Problem: Base class for a BGP ASN misconfiguration problem. """
# ==================================================================


class BGPAsnMisconfigParams(BaseModel):
    """Parameters for injecting a BGP ASN misconfiguration fault."""

    host_name: Optional[str] = Field(default=None, description="Target router host name. Defaults to a randomly selected router.")


class BGPAsnMisconfigBase:
    root_cause_category: RootCauseCategory = RootCauseCategory.MISCONFIGURATION
    root_cause_name: str = "bgp_asn_misconfig"
    TAGS: str = ["bgp"]

    Params = BGPAsnMisconfigParams

    symptom_desc = "Some hosts are experiencing connectivity issues."

    def __init__(self, scenario_name: str | None, **kwargs):
        super().__init__()
        self.net_env = get_net_env_instance(scenario_name, **kwargs)
        self.kathara_api = KatharaAPIALL(lab_name=self.net_env.lab.name)
        self.injector = FaultInjectorBase(lab_name=self.net_env.lab.name)
        self.faulty_devices = [random.choice(self.net_env.routers)]

    def inject_fault(self, params: BGPAsnMisconfigParams | None = None):
        if params is None:
            params = BGPAsnMisconfigParams()
        host = params.host_name if params.host_name is not None else self.faulty_devices[0]
        asn = self.kathara_api.exec_cmd(host, "vtysh -c 'show bgp summary' | grep 'BGP router identifier'")
        match = re.search(r"local AS number\s+(\d+)", asn)
        if match:
            as_number = int(match.group(1))
        else:
            raise ValueError("Could not find AS number in BGP summary output")
        self.injector.inject_bgp_misconfig(host_name=host, correct_asn=as_number, wrong_asn=as_number + 600)


class BGPAsnMisconfigDetection(BGPAsnMisconfigBase, DetectionTask):
    META = ProblemMeta(
        root_cause_category=BGPAsnMisconfigBase.root_cause_category,
        root_cause_name=BGPAsnMisconfigBase.root_cause_name,
        task_level=TaskLevel.DETECTION,
        description=TaskDescription.DETECTION,
    )


class BGPAsnMisconfigLocalization(BGPAsnMisconfigBase, LocalizationTask):
    META = ProblemMeta(
        root_cause_category=BGPAsnMisconfigBase.root_cause_category,
        root_cause_name=BGPAsnMisconfigBase.root_cause_name,
        task_level=TaskLevel.LOCALIZATION,
        description=TaskDescription.LOCALIZATION,
    )


class BGPAsnMisconfigRCA(BGPAsnMisconfigBase, RCATask):
    META = ProblemMeta(
        root_cause_category=BGPAsnMisconfigBase.root_cause_category,
        root_cause_name=BGPAsnMisconfigBase.root_cause_name,
        task_level=TaskLevel.RCA,
        description=TaskDescription.RCA,
    )


# ==================================================================
""" Problem: Base class for a BGP missing route advertisement problem. """
# ==================================================================


class BGPMissingAdvertiseParams(BaseModel):
    """Parameters for injecting a BGP missing route advertisement fault."""

    host_name: Optional[str] = Field(default=None, description="Target router host name. Defaults to a randomly selected router.")


class BGPMissingAdvertiseBase:
    root_cause_category: RootCauseCategory = RootCauseCategory.MISCONFIGURATION
    root_cause_name: str = "bgp_missing_route_advertisement"
    TAGS: str = ["bgp"]

    Params = BGPMissingAdvertiseParams

    def __init__(self, scenario_name: str | None, **kwargs):
        super().__init__()
        self.net_env = get_net_env_instance(scenario_name, **kwargs)
        self.kathara_api = KatharaAPIALL(lab_name=self.net_env.lab.name)
        self.injector = FaultInjectorBase(lab_name=self.net_env.lab.name)
        self.faulty_devices = [random.choice(self.net_env.routers)]

    def inject_fault(self, params: BGPMissingAdvertiseParams | None = None):
        if params is None:
            params = BGPMissingAdvertiseParams()
        host = params.host_name if params.host_name is not None else self.faulty_devices[0]
        self.injector.inject_bgp_remove_advertisement(host_name=host)


class BGPMissingAdvertiseDetection(BGPMissingAdvertiseBase, DetectionTask):
    META = ProblemMeta(
        root_cause_category=BGPMissingAdvertiseBase.root_cause_category,
        root_cause_name=BGPMissingAdvertiseBase.root_cause_name,
        task_level=TaskLevel.DETECTION,
        description=TaskDescription.DETECTION,
    )


class BGPMissingAdvertiseLocalization(BGPMissingAdvertiseBase, LocalizationTask):
    META = ProblemMeta(
        root_cause_category=BGPMissingAdvertiseBase.root_cause_category,
        root_cause_name=BGPMissingAdvertiseBase.root_cause_name,
        task_level=TaskLevel.LOCALIZATION,
        description=TaskDescription.LOCALIZATION,
    )


class BGPMissingAdvertiseRCA(BGPMissingAdvertiseBase, RCATask):
    META = ProblemMeta(
        root_cause_category=BGPMissingAdvertiseBase.root_cause_category,
        root_cause_name=BGPMissingAdvertiseBase.root_cause_name,
        task_level=TaskLevel.RCA,
        description=TaskDescription.RCA,
    )


# ==================================================================
""" Problem: BGP static blackhole route misconfiguration problem. """
# ==================================================================


class StaticBlackHoleParams(BaseModel):
    """Parameters for injecting a static blackhole route fault."""

    host_name: Optional[str] = Field(default=None, description="Target router host name. Defaults to a randomly selected router with connected hosts.")


class StaticBlackHoleBase:
    root_cause_category: RootCauseCategory = RootCauseCategory.MISCONFIGURATION
    root_cause_name: str = "host_static_blackhole"
    TAGS: str = ["bgp"]

    Params = StaticBlackHoleParams

    def __init__(self, scenario_name: str | None, **kwargs):
        super().__init__()
        self.net_env = get_net_env_instance(scenario_name, **kwargs)
        self.kathara_api = KatharaAPIALL(lab_name=self.net_env.lab.name)
        self.injector = FaultInjectorBase(lab_name=self.net_env.lab.name)
        for router in random.sample(self.net_env.routers, len(self.net_env.routers)):
            connected_devices = self.kathara_api.get_connected_devices(router)
            connected_hosts = [dev for dev in connected_devices if "switch" not in dev and "router" not in dev]
            if connected_hosts:
                self.faulty_devices = [router]
                self.victim_device = connected_hosts[0]
                self.victim_ip = self.kathara_api.get_host_ip(self.victim_device, with_prefix=False)
                break

    def inject_fault(self, params: StaticBlackHoleParams | None = None):
        if params is None:
            params = StaticBlackHoleParams()
        host = params.host_name if params.host_name is not None else self.faulty_devices[0]
        host_network = ipaddress.ip_network(
            self.kathara_api.get_host_ip(self.victim_device, with_prefix=True), strict=False
        )
        self.injector.inject_add_route_blackhole_nexthop(host_name=host, network=host_network)


class StaticBlackHoleDetection(StaticBlackHoleBase, DetectionTask):
    META = ProblemMeta(
        root_cause_category=StaticBlackHoleBase.root_cause_category,
        root_cause_name=StaticBlackHoleBase.root_cause_name,
        task_level=TaskLevel.DETECTION,
        description=TaskDescription.DETECTION,
    )


class StaticBlackHoleLocalization(StaticBlackHoleBase, LocalizationTask):
    META = ProblemMeta(
        root_cause_category=StaticBlackHoleBase.root_cause_category,
        root_cause_name=StaticBlackHoleBase.root_cause_name,
        task_level=TaskLevel.LOCALIZATION,
        description=TaskDescription.LOCALIZATION,
    )


class StaticBlackHoleRCA(StaticBlackHoleBase, RCATask):
    META = ProblemMeta(
        root_cause_category=StaticBlackHoleBase.root_cause_category,
        root_cause_name=StaticBlackHoleBase.root_cause_name,
        task_level=TaskLevel.RCA,
        description=TaskDescription.RCA,
    )


# ==================================================================
""" Problem: BGP blackhole route advertisement misconfiguration problem. """
# ==================================================================


class BGPBlackholeRouteLeakParams(BaseModel):
    """Parameters for injecting a BGP blackhole route leak fault."""

    host_name: Optional[str] = Field(default=None, description="Target router host name. Defaults to a randomly selected router with connected hosts.")


class BGPBlackholeRouteLeakBase:
    root_cause_category: RootCauseCategory = RootCauseCategory.MISCONFIGURATION
    root_cause_name: str = "bgp_blackhole_route_leak"
    TAGS: str = ["bgp"]

    Params = BGPBlackholeRouteLeakParams

    def __init__(self, scenario_name: str | None, **kwargs):
        super().__init__()
        self.net_env = get_net_env_instance(scenario_name, **kwargs)
        self.kathara_api = KatharaAPIALL(lab_name=self.net_env.lab.name)
        self.injector = FaultInjectorBase(lab_name=self.net_env.lab.name)
        for router in random.sample(self.net_env.routers, len(self.net_env.routers)):
            connected_devices = self.kathara_api.get_connected_devices(router)
            connected_hosts = [dev for dev in connected_devices if "switch" not in dev and "router" not in dev]
            if connected_hosts:
                self.faulty_devices = [router]
                self.victim_device = connected_hosts[0]
                self.victim_ip = self.kathara_api.get_host_ip(self.victim_device, with_prefix=False)
                break

    def inject_fault(self, params: BGPBlackholeRouteLeakParams | None = None):
        if params is None:
            params = BGPBlackholeRouteLeakParams()
        host = params.host_name if params.host_name is not None else self.faulty_devices[0]
        network_30 = ipaddress.ip_network(f"{self.victim_ip}/30", strict=False)
        asn_number = self.kathara_api.exec_cmd(host, "vtysh -c 'show bgp summary' | grep 'BGP router identifier'")
        match = re.search(r"local AS number\s+(\d+)", asn_number)
        if match:
            as_number = int(match.group(1))
        else:
            raise ValueError("Could not find AS number in BGP summary output")
        self.injector.inject_add_route_blackhole_advertise(host_name=host, network=network_30, AS=as_number)


class BGPBlackholeRouteLeakDetection(BGPBlackholeRouteLeakBase, DetectionTask):
    META = ProblemMeta(
        root_cause_category=BGPBlackholeRouteLeakBase.root_cause_category,
        root_cause_name=BGPBlackholeRouteLeakBase.root_cause_name,
        task_level=TaskLevel.DETECTION,
        description=TaskDescription.DETECTION,
    )


class BGPBlackholeRouteLeakLocalization(BGPBlackholeRouteLeakBase, LocalizationTask):
    META = ProblemMeta(
        root_cause_category=BGPBlackholeRouteLeakBase.root_cause_category,
        root_cause_name=BGPBlackholeRouteLeakBase.root_cause_name,
        task_level=TaskLevel.LOCALIZATION,
        description=TaskDescription.LOCALIZATION,
    )


class BGPBlackholeRouteLeakRCA(BGPBlackholeRouteLeakBase, RCATask):
    META = ProblemMeta(
        root_cause_category=BGPBlackholeRouteLeakBase.root_cause_category,
        root_cause_name=BGPBlackholeRouteLeakBase.root_cause_name,
        task_level=TaskLevel.RCA,
        description=TaskDescription.RCA,
    )


# ==================================================================
# Problem: BGP hijacking problem.
# ==================================================================


class BGPHijackingParams(BaseModel):
    """Parameters for injecting a BGP hijacking fault."""

    host_name: Optional[str] = Field(default=None, description="Target hijacking router host name. Defaults to a randomly selected router.")
    target_network: Optional[str] = Field(default=None, description="Network prefix to advertise. Defaults to runtime selection.")


class BGPHijackingBase:
    root_cause_category: RootCauseCategory = RootCauseCategory.MISCONFIGURATION
    root_cause_name: str = "bgp_hijacking"
    TAGS: str = ["bgp", "http"]

    Params = BGPHijackingParams

    def __init__(self, scenario_name: str | None, **kwargs):
        super().__init__()
        self.net_env = get_net_env_instance(scenario_name, **kwargs)
        self.kathara_api = KatharaAPIALL(lab_name=self.net_env.lab.name)
        self.injector = FaultInjectorBase(lab_name=self.net_env.lab.name)
        self.faulty_devices = [random.choice(self.net_env.routers)]
        web_server = self.net_env.servers["web"][-1]
        self.target_network = self.kathara_api.get_host_ip(web_server, with_prefix=True)
        self.target_network = str(
            ipaddress.ip_network(self.target_network, strict=False).subnets(new_prefix=25).__next__()
        )

    def inject_fault(self, params: BGPHijackingParams | None = None):
        if params is None:
            params = BGPHijackingParams()
        host = params.host_name if params.host_name is not None else self.faulty_devices[0]
        target_network = params.target_network if params.target_network is not None else self.target_network
        asn_number = self.kathara_api.frr_get_bgp_asn_number(self.faulty_devices)
        self.injector.inject_bgp_add_interface(host_name=host, intf_name="lo", ip_address=target_network)
        self.injector.inject_bgp_add_advertisement(host_name=host, network=target_network, AS=asn_number)


class BGPHijackingDetection(BGPHijackingBase, DetectionTask):
    META = ProblemMeta(
        root_cause_category=BGPHijackingBase.root_cause_category,
        root_cause_name=BGPHijackingBase.root_cause_name,
        task_level=TaskLevel.DETECTION,
        description=TaskDescription.DETECTION,
    )


class BGPHijackingLocalization(BGPHijackingBase, LocalizationTask):
    META = ProblemMeta(
        root_cause_category=BGPHijackingBase.root_cause_category,
        root_cause_name=BGPHijackingBase.root_cause_name,
        task_level=TaskLevel.LOCALIZATION,
        description=TaskDescription.LOCALIZATION,
    )


class BGPHijackingRCA(BGPHijackingBase, RCATask):
    META = ProblemMeta(
        root_cause_category=BGPHijackingBase.root_cause_category,
        root_cause_name=BGPHijackingBase.root_cause_name,
        task_level=TaskLevel.RCA,
        description=TaskDescription.RCA,
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    task = BGPAsnMisconfigBase(scenario_name="dc_clos_bgp")
    task.inject_fault()
