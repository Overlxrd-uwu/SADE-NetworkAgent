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
# Problem: P4 header definition error
# ==================================================================


class P4HeaderDefinitionErrorParams(BaseModel):
    """Parameters for injecting a P4 header definition error fault."""

    host_name: Optional[str] = Field(default=None, description="Target BMv2 switch name. Defaults to runtime selection.")
    p4_name: Optional[str] = Field(default=None, description="P4 program name (without suffix). Defaults to runtime detection.")


class P4HeaderDefinitionErrorBase:
    root_cause_category = RootCauseCategory.NETWORK_NODE_ERROR
    root_cause_name = "p4_header_definition_error"
    TAGS: str = ["p4"]

    Params = P4HeaderDefinitionErrorParams

    def __init__(self, scenario_name: str | None, **kwargs):
        super().__init__()
        self.net_env = get_net_env_instance(scenario_name, **kwargs)
        self.kathara_api = KatharaAPIALL(lab_name=self.net_env.lab.name)
        self.injector = FaultInjectorBase(lab_name=self.net_env.lab.name)
        self.faulty_devices = [random.choice(self.net_env.bmv2_switches)]
        self.p4_name = self.kathara_api.exec_cmd(self.faulty_devices[0], "echo *.p4 | sed 's/\\.p4//'")

    def inject_fault(self, params: P4HeaderDefinitionErrorParams | None = None):
        if params is None:
            params = P4HeaderDefinitionErrorParams()
        host = params.host_name if params.host_name is not None else self.faulty_devices[0]
        p4_name = params.p4_name if params.p4_name is not None else self.p4_name
        self.kathara_api.exec_cmd(
            host,
            f"cp {p4_name}.p4 {p4_name}.p4.bak && "
            f"rm {p4_name}.json && "
            f"sed -Ei 's/bit<16>[[:space:]]+identification;/bit<6>   identification;/g' {p4_name}.p4 ",
        )
        self.kathara_api.exec_cmd(host, "pkill -f simple_switch")
        self.kathara_api.exec_cmd(host, f"./hostlab/{host}.startup")


class P4CompilationErrorHeaderDetection(P4HeaderDefinitionErrorBase, DetectionTask):
    META = ProblemMeta(
        root_cause_category=P4HeaderDefinitionErrorBase.root_cause_category,
        root_cause_name=P4HeaderDefinitionErrorBase.root_cause_name,
        task_level=TaskLevel.DETECTION,
        description=TaskDescription.DETECTION,
    )


class P4CompilationErrorHeaderLocalization(P4HeaderDefinitionErrorBase, LocalizationTask):
    META = ProblemMeta(
        root_cause_category=P4HeaderDefinitionErrorBase.root_cause_category,
        root_cause_name=P4HeaderDefinitionErrorBase.root_cause_name,
        task_level=TaskLevel.LOCALIZATION,
        description=TaskDescription.LOCALIZATION,
    )


class P4CompilationErrorHeaderRCA(P4HeaderDefinitionErrorBase, RCATask):
    META = ProblemMeta(
        root_cause_category=P4HeaderDefinitionErrorBase.root_cause_category,
        root_cause_name=P4HeaderDefinitionErrorBase.root_cause_name,
        task_level=TaskLevel.RCA,
        description=TaskDescription.RCA,
    )


# ==================================================================
# Problem: P4 compilation error due to parser state issue
# ==================================================================


class P4CompilationErrorParserStateParams(BaseModel):
    """Parameters for injecting a P4 parser state compilation error fault."""

    host_name: Optional[str] = Field(default=None, description="Target BMv2 switch name. Defaults to runtime selection.")
    p4_name: Optional[str] = Field(default=None, description="P4 program name (without suffix). Defaults to runtime detection.")


class P4CompilationErrorParserStateBase:
    root_cause_category = RootCauseCategory.NETWORK_NODE_ERROR
    root_cause_name = "p4_compilation_error_parser_state"
    TAGS: str = ["p4"]

    Params = P4CompilationErrorParserStateParams

    def __init__(self, scenario_name: str | None, **kwargs):
        super().__init__()
        self.net_env = get_net_env_instance(scenario_name, **kwargs)
        self.kathara_api = KatharaAPIALL(lab_name=self.net_env.lab.name)
        self.injector = FaultInjectorBase(lab_name=self.net_env.lab.name)
        self.faulty_devices = [random.choice(self.net_env.bmv2_switches)]
        self.p4_name = self.kathara_api.exec_cmd(self.faulty_devices[0], "echo *.p4 | sed 's/\\.p4//'")

    def inject_fault(self, params: P4CompilationErrorParserStateParams | None = None):
        if params is None:
            params = P4CompilationErrorParserStateParams()
        host = params.host_name if params.host_name is not None else self.faulty_devices[0]
        p4_name = params.p4_name if params.p4_name is not None else self.p4_name
        self.kathara_api.exec_cmd(
            host,
            f"cp {p4_name}.p4 {p4_name}.p4.bak && "
            f"rm {p4_name}.json && "
            f"sed -Ei 's/state /states /g' {p4_name}.p4 ",
        )
        self.kathara_api.exec_cmd(host, "pkill -f simple_switch")
        self.kathara_api.exec_cmd(host, f"./hostlab/{host}.startup")


class P4CompilationErrorParserStateDetection(P4CompilationErrorParserStateBase, DetectionTask):
    META = ProblemMeta(
        root_cause_category=P4CompilationErrorParserStateBase.root_cause_category,
        root_cause_name=P4CompilationErrorParserStateBase.root_cause_name,
        task_level=TaskLevel.DETECTION,
        description=TaskDescription.DETECTION,
    )


class P4CompilationErrorParserStateLocalization(P4CompilationErrorParserStateBase, LocalizationTask):
    META = ProblemMeta(
        root_cause_category=P4CompilationErrorParserStateBase.root_cause_category,
        root_cause_name=P4CompilationErrorParserStateBase.root_cause_name,
        task_level=TaskLevel.LOCALIZATION,
        description=TaskDescription.LOCALIZATION,
    )


class P4CompilationErrorParserStateRCA(P4CompilationErrorParserStateBase, RCATask):
    META = ProblemMeta(
        root_cause_category=P4CompilationErrorParserStateBase.root_cause_category,
        root_cause_name=P4CompilationErrorParserStateBase.root_cause_name,
        task_level=TaskLevel.RCA,
        description=TaskDescription.RCA,
    )


# ==================================================================
# Problem: P4 table entry missing
# ==================================================================


class P4TableEntryMissingParams(BaseModel):
    """Parameters for injecting a P4 table entry missing fault."""

    host_name: Optional[str] = Field(default=None, description="Target BMv2 switch name. Defaults to runtime selection.")


class P4TableEntryMissingBase:
    root_cause_category = RootCauseCategory.NETWORK_NODE_ERROR
    root_cause_name = "p4_table_entry_missing"
    TAGS: str = ["p4"]

    Params = P4TableEntryMissingParams

    def __init__(self, scenario_name: str | None, **kwargs):
        super().__init__()
        self.net_env = get_net_env_instance(scenario_name, **kwargs)
        self.kathara_api = KatharaAPIALL(lab_name=self.net_env.lab.name)
        self.injector = FaultInjectorBase(lab_name=self.net_env.lab.name)
        self.faulty_devices = [random.choice(self.net_env.bmv2_switches)]

    def inject_fault(self, params: P4TableEntryMissingParams | None = None):
        if params is None:
            params = P4TableEntryMissingParams()
        host = params.host_name if params.host_name is not None else self.faulty_devices[0]
        self.kathara_api.exec_cmd(host, "simple_switch_CLI <<< 'table_clear MyIngress.ipv4_lpm'")
        logger.info(f"Injected fault: Deleted table entries on {host}")


class P4TableEntryMissingDetection(P4TableEntryMissingBase, DetectionTask):
    META = ProblemMeta(
        root_cause_category=P4TableEntryMissingBase.root_cause_category,
        root_cause_name=P4TableEntryMissingBase.root_cause_name,
        task_level=TaskLevel.DETECTION,
        description=TaskDescription.DETECTION,
    )


class P4TableEntryMissingLocalization(P4TableEntryMissingBase, LocalizationTask):
    META = ProblemMeta(
        root_cause_category=P4TableEntryMissingBase.root_cause_category,
        root_cause_name=P4TableEntryMissingBase.root_cause_name,
        task_level=TaskLevel.LOCALIZATION,
        description=TaskDescription.LOCALIZATION,
    )


class P4TableEntryMissingRCA(P4TableEntryMissingBase, RCATask):
    META = ProblemMeta(
        root_cause_category=P4TableEntryMissingBase.root_cause_category,
        root_cause_name=P4TableEntryMissingBase.root_cause_name,
        task_level=TaskLevel.RCA,
        description=TaskDescription.RCA,
    )


# ==================================================================
# Problem: P4 table entry misconfig
# ==================================================================


class P4TableEntryMisconfigParams(BaseModel):
    """Parameters for injecting a P4 table entry misconfiguration fault."""

    host_name: Optional[str] = Field(default=None, description="Target BMv2 switch name. Defaults to the first switch.")


class P4TableEntryMisconfigBase:
    root_cause_category = RootCauseCategory.NETWORK_NODE_ERROR
    root_cause_name = "p4_table_entry_misconfig"
    TAGS: str = ["p4"]

    Params = P4TableEntryMisconfigParams

    def __init__(self, scenario_name: str | None, **kwargs):
        super().__init__()
        self.net_env = get_net_env_instance(scenario_name, **kwargs)
        self.kathara_api = KatharaAPIALL(lab_name=self.net_env.lab.name)
        self.injector = FaultInjectorBase(lab_name=self.net_env.lab.name)
        self.faulty_devices = [self.net_env.bmv2_switches[0]]

    def inject_fault(self, params: P4TableEntryMisconfigParams | None = None):
        if params is None:
            params = P4TableEntryMisconfigParams()
        host = params.host_name if params.host_name is not None else self.faulty_devices[0]
        self.kathara_api.exec_cmd(host, "simple_switch_CLI <<< 'table_clear MyIngress.ipv4_lpm'")
        self.kathara_api.exec_cmd(host, "sed -Ei.bak 's/00:00:/66:66:/g' commands.txt")
        self.kathara_api.exec_cmd(host, "simple_switch_CLI <<< $(cat commands.txt)")
        logger.info(f"Injected fault: Modified table entries on {host}")


class P4TableEntryMisconfigDetection(P4TableEntryMisconfigBase, DetectionTask):
    META = ProblemMeta(
        root_cause_category=P4TableEntryMisconfigBase.root_cause_category,
        root_cause_name=P4TableEntryMisconfigBase.root_cause_name,
        task_level=TaskLevel.DETECTION,
        description=TaskDescription.DETECTION,
    )


class P4TableEntryMisconfigLocalization(P4TableEntryMisconfigBase, LocalizationTask):
    META = ProblemMeta(
        root_cause_category=P4TableEntryMisconfigBase.root_cause_category,
        root_cause_name=P4TableEntryMisconfigBase.root_cause_name,
        task_level=TaskLevel.LOCALIZATION,
        description=TaskDescription.LOCALIZATION,
    )


class P4TableEntryMisconfigRCA(P4TableEntryMisconfigBase, RCATask):
    META = ProblemMeta(
        root_cause_category=P4TableEntryMisconfigBase.root_cause_category,
        root_cause_name=P4TableEntryMisconfigBase.root_cause_name,
        task_level=TaskLevel.RCA,
        description=TaskDescription.RCA,
    )


# ==================================================================
# Problem: MPLS Label Limit Exceeded
# ==================================================================


class P4MPLSLabelLimitExceededParams(BaseModel):
    """Parameters for injecting an MPLS label limit exceeded fault."""

    host_name: Optional[str] = Field(default=None, description="Target BMv2 switch name. Defaults to runtime selection.")


class P4MPLSLabelLimitExceededBase:
    root_cause_category = RootCauseCategory.NETWORK_NODE_ERROR
    root_cause_name = "mpls_label_limit_exceeded"

    TAGS: str = ["mpls"]

    Params = P4MPLSLabelLimitExceededParams

    def __init__(self, scenario_name: str | None, **kwargs):
        super().__init__()
        self.net_env = get_net_env_instance(scenario_name, **kwargs)
        self.kathara_api = KatharaAPIALL(lab_name=self.net_env.lab.name)
        self.injector = FaultInjectorBase(lab_name=self.net_env.lab.name)
        self.faulty_devices = [random.choice(self.net_env.bmv2_switches)]
        self.logger = system_logger

    def inject_fault(self, params: P4MPLSLabelLimitExceededParams | None = None):
        if params is None:
            params = P4MPLSLabelLimitExceededParams()
        host = params.host_name if params.host_name is not None else self.faulty_devices[0]
        self.kathara_api.exec_cmd(
            host,
            "cp mpls.p4 mpls.p4.bak && "
            "rm mpls.json && "
            "sed -Ei 's/#define[[:space:]]+CONST_MAX_LABELS[[:space:]]+10/#define CONST_MAX_LABELS 2/g' mpls.p4 ",
        )
        self.kathara_api.exec_cmd(host, "pkill -f simple_switch")
        self.kathara_api.exec_cmd(host, f"./hostlab/{host}.startup")
        self.logger.info(f"Injected MPLS label limit exceeded fault on device: {host}")


class P4MPLSLabelLimitExceededDetection(P4MPLSLabelLimitExceededBase, DetectionTask):
    META = ProblemMeta(
        root_cause_category=P4MPLSLabelLimitExceededBase.root_cause_category,
        root_cause_name=P4MPLSLabelLimitExceededBase.root_cause_name,
        task_level=TaskLevel.DETECTION,
        description=TaskDescription.DETECTION,
    )


class P4MPLSLabelLimitExceededLocalization(P4MPLSLabelLimitExceededBase, LocalizationTask):
    META = ProblemMeta(
        root_cause_category=P4MPLSLabelLimitExceededBase.root_cause_category,
        root_cause_name=P4MPLSLabelLimitExceededBase.root_cause_name,
        task_level=TaskLevel.LOCALIZATION,
        description=TaskDescription.LOCALIZATION,
    )


class P4MPLSLabelLimitExceededRCA(P4MPLSLabelLimitExceededBase, RCATask):
    META = ProblemMeta(
        root_cause_category=P4MPLSLabelLimitExceededBase.root_cause_category,
        root_cause_name=P4MPLSLabelLimitExceededBase.root_cause_name,
        task_level=TaskLevel.RCA,
        description=TaskDescription.RCA,
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    problem = P4TableEntryMisconfigBase()
    # problem.inject_fault()
