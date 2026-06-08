import random
from typing import Optional

from pydantic import BaseModel, Field

from nika.generator.fault.injector_base import FaultInjectorBase
from nika.net_env.net_env_pool import get_net_env_instance
from nika.orchestrator.problems.problem_base import ProblemMeta, RootCauseCategory, TaskDescription, TaskLevel
from nika.orchestrator.tasks.detection import DetectionTask
from nika.orchestrator.tasks.localization import LocalizationTask
from nika.orchestrator.tasks.rca import RCATask
from nika.service.kathara import KatharaBaseAPI

# ==================================================================
# Problem: Link failure by ip link down on host interface
# ==================================================================


class LinkFailureParams(BaseModel):
    """Parameters for injecting a link-down fault."""

    host_name: Optional[str] = Field(
        default=None,
        description="Target host name. Defaults to a randomly selected host when not set.",
    )
    intf_name: str = Field(default="eth0", description="Target interface name.")


class LinkFailureBase:
    root_cause_category: RootCauseCategory = RootCauseCategory.LINK_FAILURE
    root_cause_name: str = "link_down"
    TAGS: str = ["link"]

    Params = LinkFailureParams

    symptom_desc = "Users report connectivity issues to other hosts."

    def __init__(self, scenario_name: str | None, **kwargs):
        super().__init__()
        self.net_env = get_net_env_instance(scenario_name, **kwargs)
        self.kathara_api = KatharaBaseAPI(lab_name=self.net_env.lab.name)
        self.injector = FaultInjectorBase(lab_name=self.net_env.lab.name)
        self.faulty_devices = [random.choice(self.net_env.hosts)]
        self.faulty_intf = "eth0"
        self.down_time = 1
        self.up_time = 1

    def inject_fault(self, params: LinkFailureParams | None = None):
        if params is None:
            params = LinkFailureParams()
        host = params.host_name if params.host_name is not None else self.faulty_devices[0]
        self.injector.inject_intf_down(
            host_name=host,
            intf_name=params.intf_name,
        )


class LinkFailureDetection(LinkFailureBase, DetectionTask):
    META = ProblemMeta(
        root_cause_category=LinkFailureBase.root_cause_category,
        root_cause_name=LinkFailureBase.root_cause_name,
        task_level=TaskLevel.DETECTION,
        description=TaskDescription.DETECTION,
    )


class LinkFailureLocalization(LinkFailureBase, LocalizationTask):
    META = ProblemMeta(
        root_cause_category=LinkFailureBase.root_cause_category,
        root_cause_name=LinkFailureBase.root_cause_name,
        task_level=TaskLevel.LOCALIZATION,
        description=TaskDescription.LOCALIZATION,
    )


class LinkFailureRCA(LinkFailureBase, RCATask):
    META = ProblemMeta(
        root_cause_category=LinkFailureBase.root_cause_category,
        root_cause_name=LinkFailureBase.root_cause_name,
        task_level=TaskLevel.RCA,
        description=TaskDescription.RCA,
    )


# ==========================================
# Problem: Link flapping by manual script
# ==========================================


class LinkFlapParams(BaseModel):
    """Parameters for injecting a link-flap fault."""

    host_name: Optional[str] = Field(
        default=None,
        description="Target host name. Defaults to a randomly selected host when not set.",
    )
    intf_name: str = Field(default="eth0", description="Target interface name.")
    down_time: int = Field(default=1, description="Down duration in seconds.")
    up_time: int = Field(default=1, description="Up duration in seconds.")


class LinkFlapBase:
    root_cause_category: RootCauseCategory = RootCauseCategory.LINK_FAILURE
    root_cause_name: str = "link_flap"
    TAGS: str = ["link"]

    Params = LinkFlapParams

    symptom_desc = "Users report connectivity issues to other hosts."

    def __init__(self, scenario_name: str | None, **kwargs):
        super().__init__()
        self.net_env = get_net_env_instance(scenario_name, **kwargs)
        self.kathara_api = KatharaBaseAPI(lab_name=self.net_env.lab.name)
        self.injector = FaultInjectorBase(lab_name=self.net_env.lab.name)
        self.faulty_devices = [random.choice(self.net_env.hosts)]
        self.faulty_intf = "eth0"

    def inject_fault(self, params: LinkFlapParams | None = None):
        if params is None:
            params = LinkFlapParams()
        host = params.host_name if params.host_name is not None else self.faulty_devices[0]
        self.injector.inject_link_flap(
            host_name=host,
            intf_name=params.intf_name,
            down_time=params.down_time,
            up_time=params.up_time,
        )


class LinkFlapDetection(LinkFlapBase, DetectionTask):
    META = ProblemMeta(
        root_cause_category=LinkFlapBase.root_cause_category,
        root_cause_name=LinkFlapBase.root_cause_name,
        task_level=TaskLevel.DETECTION,
        description=TaskDescription.DETECTION,
    )


class LinkFlapLocalization(LinkFlapBase, LocalizationTask):
    META = ProblemMeta(
        root_cause_category=LinkFlapBase.root_cause_category,
        root_cause_name=LinkFlapBase.root_cause_name,
        task_level=TaskLevel.LOCALIZATION,
        description=TaskDescription.LOCALIZATION,
    )


class LinkFlapRCA(LinkFlapBase, RCATask):
    META = ProblemMeta(
        root_cause_category=LinkFlapBase.root_cause_category,
        root_cause_name=LinkFlapBase.root_cause_name,
        task_level=TaskLevel.RCA,
        description=TaskDescription.RCA,
    )


# ==========================================
# Problem: Link detached. Note: the recover is not working
# ==========================================


class LinkDetachParams(BaseModel):
    """Parameters for injecting a link-detach fault."""

    host_name: Optional[str] = Field(
        default=None,
        description="Target host name. Defaults to a randomly selected host when not set.",
    )
    intf_name: str = Field(default="eth0", description="Target interface name.")


class LinkDetachBase:
    root_cause_category: RootCauseCategory = RootCauseCategory.LINK_FAILURE
    root_cause_name: str = "link_detach"
    TAGS: str = ["link"]

    Params = LinkDetachParams

    symptom_desc = "Users report connectivity issues to other hosts."

    def __init__(self, scenario_name: str | None, **kwargs):
        super().__init__()
        self.net_env = get_net_env_instance(scenario_name, **kwargs)
        self.kathara_api = KatharaBaseAPI(lab_name=self.net_env.lab.name)
        self.injector = FaultInjectorBase(lab_name=self.net_env.lab.name)
        self.faulty_devices = [random.choice(self.net_env.hosts)]
        self.faulty_intf = "eth0"

    def inject_fault(self, params: LinkDetachParams | None = None):
        if params is None:
            params = LinkDetachParams()
        host = params.host_name if params.host_name is not None else self.faulty_devices[0]
        self.injector.inject_link_detach(
            host_name=host,
            intf_name=params.intf_name,
        )


class LinkDetachDetection(LinkDetachBase, DetectionTask):
    META = ProblemMeta(
        root_cause_category=LinkDetachBase.root_cause_category,
        root_cause_name=LinkDetachBase.root_cause_name,
        task_level=TaskLevel.DETECTION,
        description=TaskDescription.DETECTION,
    )


class LinkDetachLocalization(LinkDetachBase, LocalizationTask):
    META = ProblemMeta(
        root_cause_category=LinkDetachBase.root_cause_category,
        root_cause_name=LinkDetachBase.root_cause_name,
        task_level=TaskLevel.LOCALIZATION,
        description=TaskDescription.LOCALIZATION,
    )


class LinkDetachRCA(LinkDetachBase, RCATask):
    META = ProblemMeta(
        root_cause_category=LinkDetachBase.root_cause_category,
        root_cause_name=LinkDetachBase.root_cause_name,
        task_level=TaskLevel.RCA,
        description=TaskDescription.RCA,
    )


# ==========================================
# Problem: Link fragmentation disabled, drop large packets
# ==========================================


class LinkFragParams(BaseModel):
    """Parameters for injecting a link-fragmentation-disabled fault."""

    host_name: Optional[str] = Field(
        default=None,
        description="Target host name. Defaults to a randomly selected host when not set.",
    )
    mtu: int = Field(default=10, description="Packet size threshold.")


class LinkFragBase:
    root_cause_category: RootCauseCategory = RootCauseCategory.LINK_FAILURE
    root_cause_name: str = "link_fragmentation_disabled"
    TAGS: str = ["link"]

    Params = LinkFragParams

    symptom_desc = "Users report partial packet loss when communicating with other hosts."

    def __init__(self, scenario_name: str | None, **kwargs):
        super().__init__()
        self.net_env = get_net_env_instance(scenario_name, **kwargs)
        self.kathara_api = KatharaBaseAPI(lab_name=self.net_env.lab.name)
        self.injector = FaultInjectorBase(lab_name=self.net_env.lab.name)
        self.faulty_devices = [random.choice(self.net_env.hosts)]
        self.mtu = 10

    def inject_fault(self, params: LinkFragParams | None = None):
        if params is None:
            params = LinkFragParams()
        host = params.host_name if params.host_name is not None else self.faulty_devices[0]
        self.injector.inject_fragmentation_disabled(host_name=host, mtu=params.mtu)


class LinkFragDetection(LinkFragBase, DetectionTask):
    META = ProblemMeta(
        root_cause_category=LinkFragBase.root_cause_category,
        root_cause_name=LinkFragBase.root_cause_name,
        task_level=TaskLevel.DETECTION,
        description=TaskDescription.DETECTION,
    )


class LinkFragLocalization(LinkFragBase, LocalizationTask):
    META = ProblemMeta(
        root_cause_category=LinkFragBase.root_cause_category,
        root_cause_name=LinkFragBase.root_cause_name,
        task_level=TaskLevel.LOCALIZATION,
        description=TaskDescription.LOCALIZATION,
    )


class LinkFragRCA(LinkFragBase, RCATask):
    META = ProblemMeta(
        root_cause_category=LinkFragBase.root_cause_category,
        root_cause_name=LinkFragBase.root_cause_name,
        task_level=TaskLevel.RCA,
        description=TaskDescription.RCA,
    )


if __name__ == "__main__":
    task = LinkFailureDetection()
    # task.inject_fault()
    # Here you would typically run your detection logic
