import random
from typing import Optional

from pydantic import BaseModel, Field

from nika.generator.fault.injector_host import FaultInjectorHost
from nika.generator.fault.injector_tc import FaultInjectorTC
from nika.net_env.net_env_pool import get_net_env_instance
from nika.orchestrator.problems.problem_base import ProblemMeta, RootCauseCategory, TaskDescription, TaskLevel
from nika.orchestrator.tasks.detection import DetectionTask
from nika.orchestrator.tasks.localization import LocalizationTask
from nika.orchestrator.tasks.rca import RCATask
from nika.service.kathara import KatharaAPIALL

# ==================================================================
# Problem: Web service experiencing high DNS lookup latency causing performance degradation.
# ==================================================================


class DNSLookupLatencyParams(BaseModel):
    """Parameters for injecting a DNS lookup latency fault."""

    host_name: Optional[str] = Field(default=None, description="Target DNS server host name. Defaults to runtime selection.")
    intf_name: str = Field(default="eth0", description="Interface name.")
    delay_ms: int = Field(default=1000, description="Delay in milliseconds.")


class DNSLookupLatencyBase:
    root_cause_category: RootCauseCategory = RootCauseCategory.RESOURCE_CONTENTION
    root_cause_name: str = "dns_lookup_latency"
    symptom_desc: str = "Users experience high latency when accessing web services."
    TAGS: str = ["dns", "http"]

    Params = DNSLookupLatencyParams

    def __init__(self, scenario_name: str = "dc_clos_service", **kwargs):
        super().__init__()
        self.net_env = get_net_env_instance(scenario_name, **kwargs)
        self.kathara_api = KatharaAPIALL(lab_name=self.net_env.lab.name)
        self.injector = FaultInjectorTC(lab_name=self.net_env.lab.name)
        self.faulty_devices = [random.choice(self.net_env.servers["dns"])]
        self.intf_name = "eth0"
        self.delay_ms = 1000

    def inject_fault(self, params: DNSLookupLatencyParams | None = None):
        if params is None:
            params = DNSLookupLatencyParams()
        host = params.host_name if params.host_name is not None else self.faulty_devices[0]
        self.injector.inject_delay(host_name=host, intf_name=params.intf_name, delay_ms=params.delay_ms)


class DNSLookupLatencyDetection(DNSLookupLatencyBase, DetectionTask):
    META = ProblemMeta(
        root_cause_category=DNSLookupLatencyBase.root_cause_category,
        root_cause_name=DNSLookupLatencyBase.root_cause_name,
        task_level=TaskLevel.DETECTION,
        description=TaskDescription.DETECTION,
    )


class DNSLookupLatencyLocalization(DNSLookupLatencyBase, LocalizationTask):
    META = ProblemMeta(
        root_cause_category=DNSLookupLatencyBase.root_cause_category,
        root_cause_name=DNSLookupLatencyBase.root_cause_name,
        task_level=TaskLevel.LOCALIZATION,
        description=TaskDescription.LOCALIZATION,
    )


class DNSLookupLatencyRCA(DNSLookupLatencyBase, RCATask):
    META = ProblemMeta(
        root_cause_category=DNSLookupLatencyBase.root_cause_category,
        root_cause_name=DNSLookupLatencyBase.root_cause_name,
        task_level=TaskLevel.RCA,
        description=TaskDescription.RCA,
    )


# ==================================================================
# Problem: Load balancer overload causing performance degradation.
# ==================================================================


class LoadBalancerOverloadParams(BaseModel):
    """Parameters for injecting a load balancer overload fault."""

    host_name: Optional[str] = Field(default=None, description="Target load balancer host name. Defaults to runtime selection.")
    duration: int = Field(default=300, description="Stress duration in seconds.")


class LoadBalancerOverloadBase:
    root_cause_category: RootCauseCategory = RootCauseCategory.RESOURCE_CONTENTION
    root_cause_name: str = "load_balancer_overload"
    TAGS: str = ["load_balancer", "http"]

    Params = LoadBalancerOverloadParams

    def __init__(self, scenario_name: str = "load_balancer", **kwargs):
        super().__init__()
        self.net_env = get_net_env_instance(scenario_name, **kwargs)
        self.kathara_api = KatharaAPIALL(lab_name=self.net_env.lab.name)
        self.injector = FaultInjectorHost(lab_name=self.net_env.lab.name)
        self.faulty_devices = [random.choice(self.net_env.servers["load_balancer"])]
        self.duration = 300

    def inject_fault(self, params: LoadBalancerOverloadParams | None = None):
        if params is None:
            params = LoadBalancerOverloadParams()
        host = params.host_name if params.host_name is not None else self.faulty_devices[0]
        self.injector.inject_stress_all(host_name=host, duration=params.duration)


class LoadBalancerOverloadDetection(LoadBalancerOverloadBase, DetectionTask):
    META = ProblemMeta(
        root_cause_category=LoadBalancerOverloadBase.root_cause_category,
        root_cause_name=LoadBalancerOverloadBase.root_cause_name,
        task_level=TaskLevel.DETECTION,
        description=TaskDescription.DETECTION,
    )


class LoadBalancerOverloadLocalization(LoadBalancerOverloadBase, LocalizationTask):
    META = ProblemMeta(
        root_cause_category=LoadBalancerOverloadBase.root_cause_category,
        root_cause_name=LoadBalancerOverloadBase.root_cause_name,
        task_level=TaskLevel.LOCALIZATION,
        description=TaskDescription.LOCALIZATION,
    )


class LoadBalancerOverloadRCA(LoadBalancerOverloadBase, RCATask):
    META = ProblemMeta(
        root_cause_category=LoadBalancerOverloadBase.root_cause_category,
        root_cause_name=LoadBalancerOverloadBase.root_cause_name,
        task_level=TaskLevel.RCA,
        description=TaskDescription.RCA,
    )


if __name__ == "__main__":
    problem = LoadBalancerOverloadBase()
    problem.inject_fault()
