import io
import random
import tarfile
from typing import Optional

from nika.config import pkg_path
from nika.generator.fault.injector_host import FaultInjectorHost
from nika.generator.fault.injector_tc import FaultInjectorTC
from nika.net_env.net_env_pool import get_net_env_instance
from nika.orchestrator.problems.problem_base import ProblemMeta, RootCauseCategory, TaskDescription, TaskLevel, build_verify_result
from nika.orchestrator.tasks.detection import DetectionTask
from nika.orchestrator.tasks.localization import LocalizationTask
from nika.orchestrator.tasks.rca import RCATask
from nika.service.kathara import KatharaAPIALL
from nika.service.kathara.docker_utils import get_machine_container
from nika.utils.logger import system_logger
from pydantic import BaseModel, Field

# ==================================================================
# Problem: sender resource contention. Ref. Dapper: Data Plane Performance Diagnosis of TCP
# ==================================================================


class SenderResourceContentionParams(BaseModel):
    """Parameters for injecting a sender resource contention fault."""

    host_name: Optional[str] = Field(default=None, description="Target sender host name. Defaults to runtime selection.")
    duration: int = Field(default=600, description="Stress duration in seconds.")


class SenderResourceContentionBase:
    root_cause_category: RootCauseCategory = RootCauseCategory.RESOURCE_CONTENTION
    root_cause_name: str = "sender_resource_contention"
    TAGS: str = ["http"]

    Params = SenderResourceContentionParams

    def __init__(self, scenario_name: str | None, **kwargs):
        super().__init__()
        self.net_env = get_net_env_instance(scenario_name, **kwargs)
        self.kathara_api = KatharaAPIALL(lab_name=self.net_env.lab.name)
        self.injector = FaultInjectorHost(lab_name=self.net_env.lab.name)
        self.faulty_devices = [random.choice(self.net_env.servers["web"])]
        self.duration = 600

    def inject_fault(self, params: SenderResourceContentionParams | None = None):
        if params is None:
            params = SenderResourceContentionParams()
        host = params.host_name if params.host_name is not None else self.faulty_devices[0]
        self.injector.inject_stress_all(host_name=host, duration=params.duration)
        system_logger.info(f"Injected TCP slow sender issue on host {host}")

    def verify_fault(self, params: SenderResourceContentionParams | None = None) -> dict:
        """Verify stress-ng is running on the sender host."""
        if params is None:
            params = SenderResourceContentionParams()
        host = params.host_name if params.host_name is not None else self.faulty_devices[0]
        pgrep_output = self.kathara_api.exec_cmd(host, "pgrep -a stress-ng 2>/dev/null || echo NONE").strip()
        verified = "stress-ng" in pgrep_output and pgrep_output != "NONE"
        return build_verify_result(
            root_cause_name=self.root_cause_name,
            faulty_devices=self.faulty_devices,
            verified=verified,
            details={"host": host, "pgrep_output": pgrep_output},
        )


class SenderResourceContentionDetection(SenderResourceContentionBase, DetectionTask):
    META = ProblemMeta(
        root_cause_category=SenderResourceContentionBase.root_cause_category,
        root_cause_name=SenderResourceContentionBase.root_cause_name,
        task_level=TaskLevel.DETECTION,
        description=TaskDescription.DETECTION,
    )


class SenderResourceContentionLocalization(SenderResourceContentionBase, LocalizationTask):
    META = ProblemMeta(
        root_cause_category=SenderResourceContentionBase.root_cause_category,
        root_cause_name=SenderResourceContentionBase.root_cause_name,
        task_level=TaskLevel.LOCALIZATION,
        description=TaskDescription.LOCALIZATION,
    )


class SenderResourceContentionRCA(SenderResourceContentionBase, RCATask):
    META = ProblemMeta(
        root_cause_category=SenderResourceContentionBase.root_cause_category,
        root_cause_name=SenderResourceContentionBase.root_cause_name,
        task_level=TaskLevel.RCA,
        description=TaskDescription.RCA,
    )


# ==================================================================
# Problem: Application level delay causing TCP sender issues
# ==================================================================


class SenderApplicationDelayParams(BaseModel):
    """Parameters for injecting a sender application delay fault."""

    host_name: Optional[str] = Field(default=None, description="Target sender host name. Defaults to runtime selection.")


class SenderApplicationDelayBase:
    root_cause_category: RootCauseCategory = RootCauseCategory.RESOURCE_CONTENTION
    root_cause_name: str = "sender_application_delay"
    TAGS: str = ["http"]

    Params = SenderApplicationDelayParams

    def __init__(self, scenario_name: str | None, **kwargs):
        super().__init__()
        self.net_env = get_net_env_instance(scenario_name, **kwargs)
        self.kathara_api = KatharaAPIALL(lab_name=self.net_env.lab.name)
        self.injector = FaultInjectorTC(lab_name=self.net_env.lab.name)
        self.faulty_devices = [random.choice(self.net_env.servers["web"])]

    def inject_fault(self, params: SenderApplicationDelayParams | None = None):
        if params is None:
            params = SenderApplicationDelayParams()
        host = params.host_name if params.host_name is not None else self.faulty_devices[0]
        self.kathara_api.exec_cmd(host_name=host, command="cp web_server.py web_server.py.bak")
        container = get_machine_container(lab_name=self.net_env.lab.name, host_name=host)
        src_path = str(pkg_path("net_env/utils/web/slow_sender_server.py"))
        data = io.BytesIO()
        with tarfile.open(fileobj=data, mode="w") as tar:
            tar.add(src_path, arcname="web_server.py")
        data.seek(0)
        container.put_archive(path="/", data=data)
        self.kathara_api.exec_cmd(host_name=host, command="systemctl restart web_server.service")
        system_logger.info(f"Injected TCP sender application delay issue on host {host}")

    def verify_fault(self, params: SenderApplicationDelayParams | None = None) -> dict:
        """Verify the web_server.py has a sleep call injected."""
        if params is None:
            params = SenderApplicationDelayParams()
        host = params.host_name if params.host_name is not None else self.faulty_devices[0]
        has_sleep = self.kathara_api.exec_cmd(
            host, "grep -l 'time.sleep' /web_server.py 2>/dev/null && echo yes || echo no"
        ).strip()
        verified = has_sleep == "yes"
        return build_verify_result(
            root_cause_name=self.root_cause_name,
            faulty_devices=self.faulty_devices,
            verified=verified,
            details={"host": host, "has_sleep": has_sleep},
        )


class SenderApplicationDelayDetection(SenderApplicationDelayBase, DetectionTask):
    META = ProblemMeta(
        root_cause_category=SenderApplicationDelayBase.root_cause_category,
        root_cause_name=SenderApplicationDelayBase.root_cause_name,
        task_level=TaskLevel.DETECTION,
        description=TaskDescription.DETECTION,
    )


class SenderApplicationDelayLocalization(SenderApplicationDelayBase, LocalizationTask):
    META = ProblemMeta(
        root_cause_category=SenderApplicationDelayBase.root_cause_category,
        root_cause_name=SenderApplicationDelayBase.root_cause_name,
        task_level=TaskLevel.LOCALIZATION,
        description=TaskDescription.LOCALIZATION,
    )


class SenderApplicationDelayRCA(SenderApplicationDelayBase, RCATask):
    META = ProblemMeta(
        root_cause_category=SenderApplicationDelayBase.root_cause_category,
        root_cause_name=SenderApplicationDelayBase.root_cause_name,
        task_level=TaskLevel.RCA,
        description=TaskDescription.RCA,
    )


# ==================================================================
# Problem: receiver resource contention
# ==================================================================


class ReceiverResourceContentionParams(BaseModel):
    """Parameters for injecting a receiver resource contention fault."""

    host_name: Optional[str] = Field(default=None, description="Target receiver host name. Defaults to a randomly selected host.")
    duration: int = Field(default=600, description="Stress duration in seconds.")


class ReceiverResourceContentionBase:
    root_cause_category: RootCauseCategory = RootCauseCategory.RESOURCE_CONTENTION
    root_cause_name: str = "receiver_resource_contention"
    TAGS: str = ["http"]

    Params = ReceiverResourceContentionParams

    def __init__(self, scenario_name: str | None, **kwargs):
        super().__init__()
        self.net_env = get_net_env_instance(scenario_name, **kwargs)
        self.kathara_api = KatharaAPIALL(lab_name=self.net_env.lab.name)
        self.injector = FaultInjectorHost(lab_name=self.net_env.lab.name)
        self.faulty_devices = [random.choice(self.net_env.hosts)]
        self.duration = 600

    def inject_fault(self, params: ReceiverResourceContentionParams | None = None):
        if params is None:
            params = ReceiverResourceContentionParams()
        host = params.host_name if params.host_name is not None else self.faulty_devices[0]
        self.injector.inject_stress_all(host_name=host, duration=params.duration)
        system_logger.info(f"Injected TCP receiver resource contention on host {host}")

    def verify_fault(self, params: ReceiverResourceContentionParams | None = None) -> dict:
        """Verify stress-ng is running on the receiver host."""
        if params is None:
            params = ReceiverResourceContentionParams()
        host = params.host_name if params.host_name is not None else self.faulty_devices[0]
        pgrep_output = self.kathara_api.exec_cmd(host, "pgrep -a stress-ng 2>/dev/null || echo NONE").strip()
        verified = "stress-ng" in pgrep_output and pgrep_output != "NONE"
        return build_verify_result(
            root_cause_name=self.root_cause_name,
            faulty_devices=self.faulty_devices,
            verified=verified,
            details={"host": host, "pgrep_output": pgrep_output},
        )


class ReceiverResourceContentionDetection(ReceiverResourceContentionBase, DetectionTask):
    META = ProblemMeta(
        root_cause_category=ReceiverResourceContentionBase.root_cause_category,
        root_cause_name=ReceiverResourceContentionBase.root_cause_name,
        task_level=TaskLevel.DETECTION,
        description=TaskDescription.DETECTION,
    )


class ReceiverResourceContentionLocalization(ReceiverResourceContentionBase, LocalizationTask):
    META = ProblemMeta(
        root_cause_category=ReceiverResourceContentionBase.root_cause_category,
        root_cause_name=ReceiverResourceContentionBase.root_cause_name,
        task_level=TaskLevel.LOCALIZATION,
        description=TaskDescription.LOCALIZATION,
    )


class ReceiverResourceContentionRCA(ReceiverResourceContentionBase, RCATask):
    META = ProblemMeta(
        root_cause_category=ReceiverResourceContentionBase.root_cause_category,
        root_cause_name=ReceiverResourceContentionBase.root_cause_name,
        task_level=TaskLevel.RCA,
        description=TaskDescription.RCA,
    )


if __name__ == "__main__":
    problem = ReceiverResourceContentionBase(scenario_name="ospf_enterprise_dhcp")
    problem.inject_fault()
