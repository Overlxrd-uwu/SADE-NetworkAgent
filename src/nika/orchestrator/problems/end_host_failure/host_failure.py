import random

from nika.generator.fault.injector_base import FaultInjectorBase
from nika.net_env.net_env_pool import get_net_env_instance
from nika.orchestrator.problems.problem_base import ProblemMeta, RootCauseCategory, TaskDescription, TaskLevel
from nika.orchestrator.tasks.detection import DetectionTask
from nika.orchestrator.tasks.localization import LocalizationTask
from nika.orchestrator.tasks.rca import RCATask
from nika.service.kathara import KatharaBaseAPI

# ==========================================
# Problem: Host crash simulated by killing a container
# ==========================================


class HostCrashBase:
    root_cause_category: RootCauseCategory = RootCauseCategory.END_HOST_FAILURE
    root_cause_name: str = "host_crash"
    TAGS: str = ["host"]

    def __init__(self, scenario_name: str | None, target_device: str | None = None, **kwargs):
        super().__init__()
        self.net_env = get_net_env_instance(scenario_name, **kwargs)
        self.kathara_api = KatharaBaseAPI(lab_name=self.net_env.lab.name)
        self.injector = FaultInjectorBase(lab_name=self.net_env.lab.name)
        if target_device:
            self.faulty_devices = [self._resolve_device(target_device)]
        else:
            self.faulty_devices = [random.choice(self.net_env.hosts)]

    def _resolve_device(self, target_device: str) -> str:
        """Resolve target_device to an actual topology device name.

        Returns the device as-is if it exists in the topology. Otherwise
        picks the first host whose name starts with the given prefix so
        that e.g. 'pc_0' resolves to 'pc_0_0' in dc_clos_bgp.
        """
        all_devices = (self.net_env.hosts or []) + (self.net_env.routers or [])
        if target_device in all_devices:
            return target_device
        # Try prefix match against hosts first, then all devices
        for pool in [self.net_env.hosts or [], all_devices]:
            matches = [d for d in pool if d.startswith(target_device)]
            if matches:
                return sorted(matches)[0]
        raise ValueError(
            f"target_device '{target_device}' could not be resolved to any device in the topology. "
            f"Available hosts: {self.net_env.hosts}, routers: {self.net_env.routers}"
        )

    def inject_fault(self):
        self.injector.inject_host_down(
            host_name=self.faulty_devices[0],
        )

    def recover_fault(self):
        self.injector.recover_host_down(
            host_name=self.faulty_devices[0],
        )


class HostCrashDetection(HostCrashBase, DetectionTask):
    META = ProblemMeta(
        root_cause_category=HostCrashBase.root_cause_category,
        root_cause_name=HostCrashBase.root_cause_name,
        task_level=TaskLevel.DETECTION,
        description=TaskDescription.DETECTION,
    )


class HostCrashLocalization(HostCrashBase, LocalizationTask):
    META = ProblemMeta(
        root_cause_category=HostCrashBase.root_cause_category,
        root_cause_name=HostCrashBase.root_cause_name,
        task_level=TaskLevel.LOCALIZATION,
        description=TaskDescription.LOCALIZATION,
    )


class HostCrashRCA(HostCrashBase, RCATask):
    META = ProblemMeta(
        root_cause_category=HostCrashBase.root_cause_category,
        root_cause_name=HostCrashBase.root_cause_name,
        task_level=TaskLevel.RCA,
        description=TaskDescription.RCA,
    )


if __name__ == "__main__":
    host_failure = HostCrashBase(scenario_name="simple_bgp")
    host_failure.inject_fault()
