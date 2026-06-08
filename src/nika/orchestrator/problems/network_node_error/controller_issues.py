import logging
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
# Problem: SDN controller crash
# ==================================================================


class SDNControllerCrashParams(BaseModel):
    """Parameters for injecting an SDN controller crash fault."""

    host_name: Optional[str] = Field(default=None, description="Target SDN controller host name. Defaults to runtime selection.")


class SDNControllerCrashBase:
    root_cause_category: RootCauseCategory = RootCauseCategory.NETWORK_NODE_ERROR
    root_cause_name: str = "sdn_controller_crash"
    TAGS: str = ["sdn"]

    Params = SDNControllerCrashParams

    def __init__(self, scenario_name: str | None, **kwargs):
        super().__init__()
        self.net_env = get_net_env_instance(scenario_name, **kwargs)
        self.kathara_api = KatharaAPIALL(lab_name=self.net_env.lab.name)
        self.injector = FaultInjectorBase(lab_name=self.net_env.lab.name)
        self.faulty_devices = [random.choice(self.net_env.sdn_controllers)]

    def inject_fault(self, params: SDNControllerCrashParams | None = None):
        if params is None:
            params = SDNControllerCrashParams()
        host = params.host_name if params.host_name is not None else self.faulty_devices[0]
        self.kathara_api.exec_cmd(host, "pkill -f ryu-manager")


class SDNControllerCrashDetection(SDNControllerCrashBase, DetectionTask):
    META = ProblemMeta(
        root_cause_category=SDNControllerCrashBase.root_cause_category,
        root_cause_name=SDNControllerCrashBase.root_cause_name,
        task_level=TaskLevel.DETECTION,
        description=TaskDescription.DETECTION,
    )


class SDNControllerCrashLocalization(SDNControllerCrashBase, LocalizationTask):
    META = ProblemMeta(
        root_cause_category=SDNControllerCrashBase.root_cause_category,
        root_cause_name=SDNControllerCrashBase.root_cause_name,
        task_level=TaskLevel.LOCALIZATION,
        description=TaskDescription.LOCALIZATION,
    )


class SDNControllerCrashRCA(SDNControllerCrashBase, RCATask):
    META = ProblemMeta(
        root_cause_category=SDNControllerCrashBase.root_cause_category,
        root_cause_name=SDNControllerCrashBase.root_cause_name,
        task_level=TaskLevel.RCA,
        description=TaskDescription.RCA,
    )


# ==================================================================
# Problem: Southbound port block
# ==================================================================


class SouthboundPortBlockParams(BaseModel):
    """Parameters for injecting a southbound port block fault."""

    host_name: Optional[str] = Field(default=None, description="Target SDN controller host name. Defaults to runtime selection.")
    southbound_port: int = Field(default=6633, description="Port to block.")


class SouthboundPortBlockBase:
    root_cause_category: RootCauseCategory = RootCauseCategory.NETWORK_NODE_ERROR
    root_cause_name: str = "southbound_port_block"
    TAGS: str = ["sdn"]

    Params = SouthboundPortBlockParams

    def __init__(self, scenario_name: str | None, **kwargs):
        super().__init__()
        self.net_env = get_net_env_instance(scenario_name, **kwargs)
        self.kathara_api = KatharaAPIALL(lab_name=self.net_env.lab.name)
        self.injector = FaultInjectorBase(lab_name=self.net_env.lab.name)
        self.faulty_devices = [random.choice(self.net_env.sdn_controllers)]
        self.southbound_port: int = 6633

    def inject_fault(self, params: SouthboundPortBlockParams | None = None):
        if params is None:
            params = SouthboundPortBlockParams()
        host = params.host_name if params.host_name is not None else self.faulty_devices[0]
        self.injector.inject_acl_rule(host_name=host, rule=f"tcp dport {params.southbound_port} drop")


class SouthboundPortBlockDetection(SouthboundPortBlockBase, DetectionTask):
    META = ProblemMeta(
        root_cause_category=SouthboundPortBlockBase.root_cause_category,
        root_cause_name=SouthboundPortBlockBase.root_cause_name,
        task_level=TaskLevel.DETECTION,
        description=TaskDescription.DETECTION,
    )


class SouthboundPortBlockLocalization(SouthboundPortBlockBase, LocalizationTask):
    META = ProblemMeta(
        root_cause_category=SouthboundPortBlockBase.root_cause_category,
        root_cause_name=SouthboundPortBlockBase.root_cause_name,
        task_level=TaskLevel.LOCALIZATION,
        description=TaskDescription.LOCALIZATION,
    )


class SouthboundPortBlockRCA(SouthboundPortBlockBase, RCATask):
    META = ProblemMeta(
        root_cause_category=SouthboundPortBlockBase.root_cause_category,
        root_cause_name=SouthboundPortBlockBase.root_cause_name,
        task_level=TaskLevel.RCA,
        description=TaskDescription.RCA,
    )


# ==================================================================
# Problem: Southbound port mismatch
# ==================================================================


class SouthboundPortMismatchParams(BaseModel):
    """Parameters for injecting a southbound port mismatch fault."""

    host_name: Optional[str] = Field(default=None, description="Target SDN controller host name. Defaults to runtime selection.")
    mismatched_port: int = Field(default=6653, description="Port used after restart.")
    original_port: int = Field(default=6633, description="Expected original OpenFlow port.")


class SouthboundPortMismatchBase:
    root_cause_category: RootCauseCategory = RootCauseCategory.NETWORK_NODE_ERROR
    root_cause_name: str = "southbound_port_mismatch"
    TAGS: str = ["sdn"]

    Params = SouthboundPortMismatchParams

    def __init__(self, scenario_name: str | None, **kwargs):
        super().__init__()
        self.net_env = get_net_env_instance(scenario_name, **kwargs)
        self.kathara_api = KatharaAPIALL(lab_name=self.net_env.lab.name)
        self.injector = FaultInjectorBase(lab_name=self.net_env.lab.name)
        self.faulty_devices = [random.choice(self.net_env.sdn_controllers)]
        self.original_port: int = 6633
        self.mismatched_port: int = 6653

    def inject_fault(self, params: SouthboundPortMismatchParams | None = None):
        if params is None:
            params = SouthboundPortMismatchParams()
        host = params.host_name if params.host_name is not None else self.faulty_devices[0]
        self.kathara_api.exec_cmd(host, "pkill -f ryu-manager")
        self.kathara_api.exec_cmd(host, f"ryu-manager --ofp-tcp-listen-port {params.mismatched_port} ryu.app.simple_switch &")


class SouthboundPortMismatchDetection(SouthboundPortMismatchBase, DetectionTask):
    META = ProblemMeta(
        root_cause_category=SouthboundPortMismatchBase.root_cause_category,
        root_cause_name=SouthboundPortMismatchBase.root_cause_name,
        task_level=TaskLevel.DETECTION,
        description=TaskDescription.DETECTION,
    )


class SouthboundPortMismatchLocalization(SouthboundPortMismatchBase, LocalizationTask):
    META = ProblemMeta(
        root_cause_category=SouthboundPortMismatchBase.root_cause_category,
        root_cause_name=SouthboundPortMismatchBase.root_cause_name,
        task_level=TaskLevel.LOCALIZATION,
        description=TaskDescription.LOCALIZATION,
    )


class SouthboundPortMismatchRCA(SouthboundPortMismatchBase, RCATask):
    META = ProblemMeta(
        root_cause_category=SouthboundPortMismatchBase.root_cause_category,
        root_cause_name=SouthboundPortMismatchBase.root_cause_name,
        task_level=TaskLevel.RCA,
        description=TaskDescription.RCA,
    )


# ==================================================================
# Problem: Flow rule shadowing
# ==================================================================


class FlowRuleShadowingParams(BaseModel):
    """Parameters for injecting a flow rule shadowing fault."""

    host_name: Optional[str] = Field(default=None, description="Target OVS switch name. Defaults to runtime selection.")


class FlowRuleShadowingBase:
    root_cause_category: RootCauseCategory = RootCauseCategory.NETWORK_NODE_ERROR
    root_cause_name: str = "flow_rule_shadowing"
    TAGS: str = ["sdn"]

    Params = FlowRuleShadowingParams

    def __init__(self, scenario_name: str | None, **kwargs):
        super().__init__()
        self.net_env = get_net_env_instance(scenario_name, **kwargs)
        self.kathara_api = KatharaAPIALL(lab_name=self.net_env.lab.name)
        self.injector = FaultInjectorBase(lab_name=self.net_env.lab.name)
        self.faulty_devices = [random.choice(self.net_env.ovs_switches)]

    def inject_fault(self, params: FlowRuleShadowingParams | None = None):
        if params is None:
            params = FlowRuleShadowingParams()
        host = params.host_name if params.host_name is not None else self.faulty_devices[0]
        self.kathara_api.exec_cmd(host, f"ovs-ofctl add-flow {host} 'priority=100,actions=drop'")


class FlowRuleShadowingDetection(FlowRuleShadowingBase, DetectionTask):
    META = ProblemMeta(
        root_cause_category=FlowRuleShadowingBase.root_cause_category,
        root_cause_name=FlowRuleShadowingBase.root_cause_name,
        task_level=TaskLevel.DETECTION,
        description=TaskDescription.DETECTION,
    )


class FlowRuleShadowingLocalization(FlowRuleShadowingBase, LocalizationTask):
    META = ProblemMeta(
        root_cause_category=FlowRuleShadowingBase.root_cause_category,
        root_cause_name=FlowRuleShadowingBase.root_cause_name,
        task_level=TaskLevel.LOCALIZATION,
        description=TaskDescription.LOCALIZATION,
    )


class FlowRuleShadowingRCA(FlowRuleShadowingBase, RCATask):
    META = ProblemMeta(
        root_cause_category=FlowRuleShadowingBase.root_cause_category,
        root_cause_name=FlowRuleShadowingBase.root_cause_name,
        task_level=TaskLevel.RCA,
        description=TaskDescription.RCA,
    )


# ==================================================================
# Problem: Flow rule loop
# ==================================================================


class FlowRuleLoopParams(BaseModel):
    """Parameters for injecting a flow rule loop fault."""

    host_name: Optional[str] = Field(default=None, description="Primary OVS switch name. Defaults to runtime selection.")
    host_name_2: Optional[str] = Field(default=None, description="Secondary OVS switch name. Defaults to runtime selection.")


class FlowRuleLoopBase:
    root_cause_category: RootCauseCategory = RootCauseCategory.NETWORK_NODE_ERROR
    root_cause_name: str = "flow_rule_loop"
    TAGS: str = ["sdn"]

    Params = FlowRuleLoopParams

    def __init__(self, scenario_name: str | None, **kwargs):
        super().__init__()
        self.net_env = get_net_env_instance(scenario_name, **kwargs)
        self.kathara_api = KatharaAPIALL(lab_name=self.net_env.lab.name)
        self.injector = FaultInjectorBase(lab_name=self.net_env.lab.name)
        self.faulty_devices = self.net_env.ovs_switches[:2]

    def inject_fault(self, params: FlowRuleLoopParams | None = None):
        if params is None:
            params = FlowRuleLoopParams()
        host0 = params.host_name if params.host_name is not None else self.faulty_devices[0]
        host1 = params.host_name_2 if params.host_name_2 is not None else self.faulty_devices[1]
        self.kathara_api.exec_cmd(host0, f"ovs-ofctl add-flow {host0} 'in_port=eth0,actions=output:eth0'")
        self.kathara_api.exec_cmd(host1, f"ovs-ofctl add-flow {host1} 'in_port=eth1,actions=output:eth1'")


class FlowRuleLoopDetection(FlowRuleLoopBase, DetectionTask):
    META = ProblemMeta(
        root_cause_category=FlowRuleLoopBase.root_cause_category,
        root_cause_name=FlowRuleLoopBase.root_cause_name,
        task_level=TaskLevel.DETECTION,
        description=TaskDescription.DETECTION,
    )


class FlowRuleLoopLocalization(FlowRuleLoopBase, LocalizationTask):
    META = ProblemMeta(
        root_cause_category=FlowRuleLoopBase.root_cause_category,
        root_cause_name=FlowRuleLoopBase.root_cause_name,
        task_level=TaskLevel.LOCALIZATION,
        description=TaskDescription.LOCALIZATION,
    )


class FlowRuleLoopRCA(FlowRuleLoopBase, RCATask):
    META = ProblemMeta(
        root_cause_category=FlowRuleLoopBase.root_cause_category,
        root_cause_name=FlowRuleLoopBase.root_cause_name,
        task_level=TaskLevel.RCA,
        description=TaskDescription.RCA,
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    problem = FlowRuleLoopBase()
    problem.inject_fault()
