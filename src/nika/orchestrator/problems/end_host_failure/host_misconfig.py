import logging
import random
from typing import Optional

from pydantic import BaseModel, Field

from nika.generator.fault.injector_host import FaultInjectorHost
from nika.net_env.net_env_pool import get_net_env_instance
from nika.orchestrator.problems.problem_base import ProblemMeta, RootCauseCategory, TaskDescription, TaskLevel, build_verify_result
from nika.orchestrator.tasks.detection import DetectionTask
from nika.orchestrator.tasks.localization import LocalizationTask
from nika.orchestrator.tasks.rca import RCATask
from nika.service.kathara import KatharaBaseAPI
from nika.utils.logger import system_logger

# ==========================================
# Problem: Host missing IP address
# ==========================================


class HostMissingIPParams(BaseModel):
    """Parameters for injecting a host-missing-IP fault."""

    host_name: Optional[str] = Field(default=None, description="Target host name. Defaults to a randomly selected host.")
    intf_name: str = Field(default="eth0", description="Target interface name.")


class HostMissingIPBase:
    root_cause_category: RootCauseCategory = RootCauseCategory.END_HOST_FAILURE
    root_cause_name: str = "host_missing_ip"
    TAGS: str = ["pc"]

    Params = HostMissingIPParams

    symptom_desc = "Some hosts are unable to communicate with other devices in the network."

    def __init__(self, scenario_name: str | None, **kwargs):
        super().__init__()
        self.logger = system_logger
        self.net_env = get_net_env_instance(scenario_name, **kwargs)
        self.kathara_api = KatharaBaseAPI(lab_name=self.net_env.lab.name)
        self.injector = FaultInjectorHost(lab_name=self.net_env.lab.name)
        self.faulty_devices = [random.choice(self.net_env.hosts)]
        self.incorrect_ip: str | None = None
        self.intf_name = "eth0"

    def inject_fault(self, params: HostMissingIPParams | None = None):
        if params is None:
            params = HostMissingIPParams()
        host = params.host_name if params.host_name is not None else self.faulty_devices[0]
        intf = params.intf_name
        real_ip = self.kathara_api.get_host_ip(host, intf, with_prefix=True)
        real_gateway = self.kathara_api.get_default_gateway(host)
        self.kathara_api.exec_cmd(host_name=host, command=f"ip addr del {real_ip} dev {intf}")
        self.kathara_api.exec_cmd(host_name=host, command=f"echo '{real_ip} {real_gateway}' > /tmp/removed_ip.txt")
        self.logger.info(f"Injected missing IP on {host} from {real_ip} and gateway {real_gateway}.")

    def verify_fault(self, params: HostMissingIPParams | None = None) -> dict:
        """Verify that the host has no global IPv4 address on the interface."""
        if params is None:
            params = HostMissingIPParams()
        host = params.host_name if params.host_name is not None else self.faulty_devices[0]
        intf = params.intf_name
        ip_line = self.kathara_api.exec_cmd(
            host, f"ip -4 -o addr show dev {intf} scope global"
        ).strip()
        verified = "inet " not in ip_line
        return build_verify_result(
            root_cause_name=self.root_cause_name,
            faulty_devices=self.faulty_devices,
            verified=verified,
            details={"host": host, "intf": intf, "ip_line": ip_line},
        )


class HostMissingIPDetection(HostMissingIPBase, DetectionTask):
    META = ProblemMeta(
        root_cause_category=HostMissingIPBase.root_cause_category,
        root_cause_name=HostMissingIPBase.root_cause_name,
        task_level=TaskLevel.DETECTION,
        description=TaskDescription.DETECTION,
    )


class HostMissingIPLocalization(HostMissingIPBase, LocalizationTask):
    META = ProblemMeta(
        root_cause_category=HostMissingIPBase.root_cause_category,
        root_cause_name=HostMissingIPBase.root_cause_name,
        task_level=TaskLevel.LOCALIZATION,
        description=TaskDescription.LOCALIZATION,
    )


class HostMissingIPRCA(HostMissingIPBase, RCATask):
    META = ProblemMeta(
        root_cause_category=HostMissingIPBase.root_cause_category,
        root_cause_name=HostMissingIPBase.root_cause_name,
        task_level=TaskLevel.RCA,
        description=TaskDescription.RCA,
    )


# ==========================================
""" Problem: Host IP conflict """


class HostIPConflictParams(BaseModel):
    """Parameters for injecting a host IP conflict fault."""

    host_name: Optional[str] = Field(default=None, description="Source host whose IP is copied. Defaults to runtime selection.")
    host_name_2: Optional[str] = Field(default=None, description="Target host to misconfigure. Defaults to runtime selection.")


class HostIPConflictBase:
    root_cause_category: RootCauseCategory = RootCauseCategory.END_HOST_FAILURE
    root_cause_name: str = "host_ip_conflict"
    TAGS: str = ["pc"]

    Params = HostIPConflictParams

    symptom_desc = "Some hosts experience intermittent connectivity issues."

    def __init__(self, scenario_name: str | None, **kwargs):
        super().__init__()
        self.net_env = get_net_env_instance(scenario_name, **kwargs)
        self.kathara_api = KatharaBaseAPI(lab_name=self.net_env.lab.name)
        self.injector = FaultInjectorHost(lab_name=self.net_env.lab.name)
        self.faulty_devices = random.sample(self.net_env.hosts, 2)

    def inject_fault(self, params: HostIPConflictParams | None = None):
        if params is None:
            params = HostIPConflictParams()
        src_host = params.host_name if params.host_name is not None else self.faulty_devices[0]
        dst_host = params.host_name_2 if params.host_name_2 is not None else self.faulty_devices[1]
        self.injector.inject_ip_change(
            host_name=dst_host,
            old_ip=self.kathara_api.get_host_ip(dst_host, "eth0", with_prefix=True),
            new_ip=self.kathara_api.get_host_ip(src_host, "eth0", with_prefix=True),
            intf_name="eth0",
            new_gateway=self.kathara_api.get_default_gateway(src_host),
        )

    def verify_fault(self, params: HostIPConflictParams | None = None) -> dict:
        """Verify both hosts share the same eth0 IP (conflict)."""
        if params is None:
            params = HostIPConflictParams()
        host_a = params.host_name if params.host_name is not None else self.faulty_devices[0]
        host_b = params.host_name_2 if params.host_name_2 is not None else self.faulty_devices[1]
        cmd = "ip -4 -o addr show dev eth0 scope global | awk '/inet /{print $4}'"
        ip_a_raw = self.kathara_api.exec_cmd(host_a, cmd).strip()
        ip_b_raw = self.kathara_api.exec_cmd(host_b, cmd).strip()
        ip_a = ip_a_raw.split("/")[0] if ip_a_raw else ""
        ip_b = ip_b_raw.split("/")[0] if ip_b_raw else ""
        verified = bool(ip_a) and ip_a == ip_b
        return build_verify_result(
            root_cause_name=self.root_cause_name,
            faulty_devices=self.faulty_devices,
            verified=verified,
            details={"host_a": host_a, "host_b": host_b, "ip_a": ip_a, "ip_b": ip_b},
        )


class HostIPConflictDetection(HostIPConflictBase, DetectionTask):
    META = ProblemMeta(
        root_cause_category=HostIPConflictBase.root_cause_category,
        root_cause_name=HostIPConflictBase.root_cause_name,
        task_level=TaskLevel.DETECTION,
        description=TaskDescription.DETECTION,
    )


class HostIPConflictLocalization(HostIPConflictBase, LocalizationTask):
    META = ProblemMeta(
        root_cause_category=HostIPConflictBase.root_cause_category,
        root_cause_name=HostIPConflictBase.root_cause_name,
        task_level=TaskLevel.LOCALIZATION,
        description=TaskDescription.LOCALIZATION,
    )


class HostIPConflictRCA(HostIPConflictBase, RCATask):
    META = ProblemMeta(
        root_cause_category=HostIPConflictBase.root_cause_category,
        root_cause_name=HostIPConflictBase.root_cause_name,
        task_level=TaskLevel.RCA,
        description=TaskDescription.RCA,
    )


# ==========================================
# Problem: Incorrect Host IP
# ==========================================


class HostIncorrectIPParams(BaseModel):
    """Parameters for injecting an incorrect host IP fault."""

    host_name: Optional[str] = Field(default=None, description="Target host name. Defaults to a randomly selected host.")
    incorrect_ip: Optional[str] = Field(default=None, description="Incorrect CIDR IP. Defaults to a random 10.2.1.x/24 address.")


class HostIncorrectIPBase:
    root_cause_category: RootCauseCategory = RootCauseCategory.END_HOST_FAILURE
    root_cause_name: str = "host_incorrect_ip"
    TAGS: str = ["pc"]

    Params = HostIncorrectIPParams

    symptom_desc = "Some hosts seem to be unreachable in the network."

    def __init__(self, scenario_name: str | None, **kwargs):
        super().__init__()
        self.net_env = get_net_env_instance(scenario_name, **kwargs)
        self.kathara_api = KatharaBaseAPI(lab_name=self.net_env.lab.name)
        self.injector = FaultInjectorHost(lab_name=self.net_env.lab.name)
        self.faulty_devices = [random.choice(self.net_env.hosts)]

    def inject_fault(self, params: HostIncorrectIPParams | None = None):
        if params is None:
            params = HostIncorrectIPParams()
        host = params.host_name if params.host_name is not None else self.faulty_devices[0]
        incorrect_ip = params.incorrect_ip or f"10.2.1.{random.randint(2, 254)}/24"
        ip_gateway = "10.2.1.1"
        self.injector.inject_ip_change(
            host_name=host,
            old_ip=self.kathara_api.get_host_ip(host, "eth0", with_prefix=True),
            new_ip=incorrect_ip,
            intf_name="eth0",
            new_gateway=ip_gateway,
        )

    def verify_fault(self, params: HostIncorrectIPParams | None = None) -> dict:
        """Verify that the host eth0 has an IP in the 10.2.1.x/24 range (injected incorrect range)."""
        if params is None:
            params = HostIncorrectIPParams()
        host = params.host_name if params.host_name is not None else self.faulty_devices[0]
        ip_line = self.kathara_api.exec_cmd(
            host, "ip -4 -o addr show dev eth0 scope global"
        ).strip()
        verified = "inet 10.2.1." in ip_line
        return build_verify_result(
            root_cause_name=self.root_cause_name,
            faulty_devices=self.faulty_devices,
            verified=verified,
            details={"host": host, "ip_line": ip_line},
        )


class HostIncorrectIPDetection(HostIncorrectIPBase, DetectionTask):
    META = ProblemMeta(
        root_cause_category=HostIncorrectIPBase.root_cause_category,
        root_cause_name=HostIncorrectIPBase.root_cause_name,
        task_level=TaskLevel.DETECTION,
        description=TaskDescription.DETECTION,
    )


class HostIncorrectIPLocalization(HostIncorrectIPBase, LocalizationTask):
    META = ProblemMeta(
        root_cause_category=HostIncorrectIPBase.root_cause_category,
        root_cause_name=HostIncorrectIPBase.root_cause_name,
        task_level=TaskLevel.LOCALIZATION,
        description=TaskDescription.LOCALIZATION,
    )


class HostIncorrectIPRCA(HostIncorrectIPBase, RCATask):
    META = ProblemMeta(
        root_cause_category=HostIncorrectIPBase.root_cause_category,
        root_cause_name=HostIncorrectIPBase.root_cause_name,
        task_level=TaskLevel.RCA,
        description=TaskDescription.RCA,
    )


# ==========================================
# Problem: Incorrect Host Gateway
# ==========================================


class HostIncorrectGatewayParams(BaseModel):
    """Parameters for injecting an incorrect host gateway fault."""

    host_name: Optional[str] = Field(default=None, description="Target host name. Defaults to a randomly selected host.")
    new_gateway: Optional[str] = Field(default=None, description="Incorrect gateway IP. Defaults to a derived address.")


class HostIncorrectGatewayBase:
    root_cause_category: RootCauseCategory = RootCauseCategory.END_HOST_FAILURE
    root_cause_name: str = "host_incorrect_gateway"
    TAGS: str = ["pc", "frr"]

    Params = HostIncorrectGatewayParams

    symptom_desc = "Some hosts seem to be unreachable in the network."

    def __init__(self, scenario_name: str | None, **kwargs):
        super().__init__()
        self.net_env = get_net_env_instance(scenario_name, **kwargs)
        self.kathara_api = KatharaBaseAPI(lab_name=self.net_env.lab.name)
        self.injector = FaultInjectorHost(lab_name=self.net_env.lab.name)
        self.faulty_devices = [random.choice(self.net_env.hosts)]
        self.new_gateway: str | None = None

    def inject_fault(self, params: HostIncorrectGatewayParams | None = None):
        if params is None:
            params = HostIncorrectGatewayParams()
        host = params.host_name if params.host_name is not None else self.faulty_devices[0]
        new_gateway = params.new_gateway or self.new_gateway
        if new_gateway is None:
            try:
                gw_parts = self.kathara_api.get_default_gateway(host).split(".")
                gw_parts[-1] = "254"
                new_gateway = ".".join(gw_parts)
            except Exception:
                new_gateway = "10.0.0.254"
        self.injector.inject_ip_change(
            host_name=host,
            old_ip=self.kathara_api.get_host_ip(host, "eth0", with_prefix=True),
            new_ip=self.kathara_api.get_host_ip(host, "eth0", with_prefix=True),
            intf_name="eth0",
            new_gateway=new_gateway,
        )

    def verify_fault(self, params: HostIncorrectGatewayParams | None = None) -> dict:
        """Verify that the default route gateway ends in .254 (injected wrong gateway)."""
        if params is None:
            params = HostIncorrectGatewayParams()
        host = params.host_name if params.host_name is not None else self.faulty_devices[0]
        route_line = self.kathara_api.exec_cmd(host, "ip route show default").strip()
        verified = ".254" in route_line
        return build_verify_result(
            root_cause_name=self.root_cause_name,
            faulty_devices=self.faulty_devices,
            verified=verified,
            details={"host": host, "route_line": route_line},
        )


class HostIncorrectGatewayDetection(HostIncorrectGatewayBase, DetectionTask):
    META = ProblemMeta(
        root_cause_category=HostIncorrectGatewayBase.root_cause_category,
        root_cause_name=HostIncorrectGatewayBase.root_cause_name,
        task_level=TaskLevel.DETECTION,
        description=TaskDescription.DETECTION,
    )


class HostIncorrectGatewayLocalization(HostIncorrectGatewayBase, LocalizationTask):
    META = ProblemMeta(
        root_cause_category=HostIncorrectGatewayBase.root_cause_category,
        root_cause_name=HostIncorrectGatewayBase.root_cause_name,
        task_level=TaskLevel.LOCALIZATION,
        description=TaskDescription.LOCALIZATION,
    )


class HostIncorrectGatewayRCA(HostIncorrectGatewayBase, RCATask):
    META = ProblemMeta(
        root_cause_category=HostIncorrectGatewayBase.root_cause_category,
        root_cause_name=HostIncorrectGatewayBase.root_cause_name,
        task_level=TaskLevel.RCA,
        description=TaskDescription.RCA,
    )


# ==========================================
# Problem: Incorrect Host netmask
# ==========================================


class HostIncorrectNetmaskParams(BaseModel):
    """Parameters for injecting an incorrect host netmask fault."""

    host_name: Optional[str] = Field(default=None, description="Target host name. Defaults to a randomly selected host.")
    netmask_prefix: int = Field(default=8, description="Incorrect prefix length.")


class HostIncorrectNetmaskBase:
    root_cause_category: RootCauseCategory = RootCauseCategory.END_HOST_FAILURE
    root_cause_name: str = "host_incorrect_netmask"
    TAGS: str = ["pc", "frr"]

    Params = HostIncorrectNetmaskParams

    symptom_desc = "Some hosts seem to be unreachable in the network."

    def __init__(self, scenario_name: str | None, **kwargs):
        super().__init__()
        self.net_env = get_net_env_instance(scenario_name, **kwargs)
        self.kathara_api = KatharaBaseAPI(lab_name=self.net_env.lab.name)
        self.injector = FaultInjectorHost(lab_name=self.net_env.lab.name)
        self.faulty_devices = [random.choice(self.net_env.hosts)]
        self.netmask_prefix = 8

    def inject_fault(self, params: HostIncorrectNetmaskParams | None = None):
        if params is None:
            params = HostIncorrectNetmaskParams()
        host = params.host_name if params.host_name is not None else self.faulty_devices[0]
        old_ip = self.kathara_api.get_host_ip(host, "eth0", with_prefix=True)
        ip_part = old_ip.split("/")[0]
        new_ip = f"{ip_part}/{params.netmask_prefix}"
        self.injector.inject_ip_change(
            host_name=host,
            old_ip=old_ip,
            new_ip=new_ip,
            intf_name="eth0",
            new_gateway=self.kathara_api.get_default_gateway(host),
        )

    def verify_fault(self, params: HostIncorrectNetmaskParams | None = None) -> dict:
        """Verify that eth0 has a non-/24 prefix (injected wrong netmask)."""
        if params is None:
            params = HostIncorrectNetmaskParams()
        host = params.host_name if params.host_name is not None else self.faulty_devices[0]
        expected_prefix = params.netmask_prefix
        ip_line = self.kathara_api.exec_cmd(
            host, "ip -4 -o addr show dev eth0 scope global"
        ).strip()
        prefix = None
        if "inet " in ip_line:
            parts = ip_line.split()
            for i, p in enumerate(parts):
                if p == "inet" and i + 1 < len(parts):
                    cidr = parts[i + 1]
                    if "/" in cidr:
                        prefix = int(cidr.split("/")[1])
                    break
        verified = prefix is not None and prefix != 24
        return build_verify_result(
            root_cause_name=self.root_cause_name,
            faulty_devices=self.faulty_devices,
            verified=verified,
            details={"host": host, "ip_line": ip_line, "expected_prefix": expected_prefix, "actual_prefix": prefix},
        )


class HostIncorrectNetmaskDetection(HostIncorrectNetmaskBase, DetectionTask):
    META = ProblemMeta(
        root_cause_category=HostIncorrectNetmaskBase.root_cause_category,
        root_cause_name=HostIncorrectNetmaskBase.root_cause_name,
        task_level=TaskLevel.DETECTION,
        description=TaskDescription.DETECTION,
    )


class HostIncorrectNetmaskLocalization(HostIncorrectNetmaskBase, LocalizationTask):
    META = ProblemMeta(
        root_cause_category=HostIncorrectNetmaskBase.root_cause_category,
        root_cause_name=HostIncorrectNetmaskBase.root_cause_name,
        task_level=TaskLevel.LOCALIZATION,
        description=TaskDescription.LOCALIZATION,
    )


class HostIncorrectNetmaskRCA(HostIncorrectNetmaskBase, RCATask):
    META = ProblemMeta(
        root_cause_category=HostIncorrectNetmaskBase.root_cause_category,
        root_cause_name=HostIncorrectNetmaskBase.root_cause_name,
        task_level=TaskLevel.RCA,
        description=TaskDescription.RCA,
    )


# ==========================================
# Problem: Incorrect Host DNS resolvers
# =========================================


class HostIncorrectDNSParams(BaseModel):
    """Parameters for injecting an incorrect DNS resolver fault."""

    host_name: Optional[str] = Field(default=None, description="Target host name. Defaults to a randomly selected host.")
    fake_dns_ip: str = Field(default="8.8.8.8", description="Incorrect DNS IP.")


class HostIncorrectDNSBase:
    root_cause_category: RootCauseCategory = RootCauseCategory.END_HOST_FAILURE
    root_cause_name: str = "host_incorrect_dns"
    TAGS: str = ["dns"]

    Params = HostIncorrectDNSParams

    symptom_desc = "Some hosts are unable to access web services."

    def __init__(self, scenario_name: str | None, **kwargs):
        self.net_env = get_net_env_instance(scenario_name, **kwargs)
        self.kathara_api = KatharaBaseAPI(lab_name=self.net_env.lab.name)
        self.injector = FaultInjectorHost(lab_name=self.net_env.lab.name)
        self.faulty_devices = [random.choice(self.net_env.hosts)]
        self.fake_dns_ip = "8.8.8.8"

    def inject_fault(self, params: HostIncorrectDNSParams | None = None):
        if params is None:
            params = HostIncorrectDNSParams()
        host = params.host_name if params.host_name is not None else self.faulty_devices[0]
        self.injector.inject_dns_misconfiguration(host_name=host, fake_dns_ip=params.fake_dns_ip)

    def verify_fault(self, params: HostIncorrectDNSParams | None = None) -> dict:
        """Verify the incorrect-DNS fault by checking /etc/resolv.conf contains the fake DNS IP."""
        if params is None:
            params = HostIncorrectDNSParams()
        host = params.host_name if params.host_name is not None else self.faulty_devices[0]
        fake_dns_ip = params.fake_dns_ip
        resolv = self.kathara_api.exec_cmd(host, "cat /etc/resolv.conf 2>/dev/null || echo ''")
        verified = fake_dns_ip in resolv
        return build_verify_result(
            root_cause_name=self.root_cause_name,
            faulty_devices=self.faulty_devices,
            verified=verified,
            details={"host": host, "fake_dns_ip": fake_dns_ip, "resolv_conf": resolv.strip()},
        )


class HostIncorrectDNSDetection(HostIncorrectDNSBase, DetectionTask):
    META = ProblemMeta(
        root_cause_category=HostIncorrectDNSBase.root_cause_category,
        root_cause_name=HostIncorrectDNSBase.root_cause_name,
        task_level=TaskLevel.DETECTION,
        description=TaskDescription.DETECTION,
    )


class HostIncorrectDNSLocalization(HostIncorrectDNSBase, LocalizationTask):
    META = ProblemMeta(
        root_cause_category=HostIncorrectDNSBase.root_cause_category,
        root_cause_name=HostIncorrectDNSBase.root_cause_name,
        task_level=TaskLevel.LOCALIZATION,
        description=TaskDescription.LOCALIZATION,
    )


class HostIncorrectDNSRCA(HostIncorrectDNSBase, RCATask):
    META = ProblemMeta(
        root_cause_category=HostIncorrectDNSBase.root_cause_category,
        root_cause_name=HostIncorrectDNSBase.root_cause_name,
        task_level=TaskLevel.RCA,
        description=TaskDescription.RCA,
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
