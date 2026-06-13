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
# Problem: VPN membership missing on end host causing inability to access services over VPN.
# ==========================================


class VPNMembershipMissingParams(BaseModel):
    """Parameters for injecting a VPN membership missing fault."""

    host_name: Optional[str] = Field(default=None, description="Target host to remove from VPN. Defaults to runtime selection.")
    host_name_2: Optional[str] = Field(default=None, description="VPN server host name. Defaults to runtime selection.")


class VPNMembershipMissingBase:
    root_cause_category: RootCauseCategory = RootCauseCategory.END_HOST_FAILURE
    root_cause_name: str = "host_vpn_membership_missing"
    TAGS: str = ["vpn"]

    Params = VPNMembershipMissingParams

    def __init__(self, scenario_name: str | None, **kwargs):
        super().__init__()
        self.logger = system_logger
        self.net_env = get_net_env_instance(scenario_name, **kwargs)
        self.kathara_api = KatharaBaseAPI(lab_name=self.net_env.lab.name)
        self.injector = FaultInjectorHost(lab_name=self.net_env.lab.name)
        self.vpn_server = self.net_env.servers["vpn"][0]
        self.target_host = random.choice(["pc1", "web_server_1_1", "web_server_1_2"])
        self.faulty_devices = [self.target_host, self.vpn_server]

    def inject_fault(self, params: VPNMembershipMissingParams | None = None):
        if params is None:
            params = VPNMembershipMissingParams()
        target_host = params.host_name if params.host_name is not None else self.target_host
        vpn_server = params.host_name_2 if params.host_name_2 is not None else self.vpn_server

        self.kathara_api.exec_cmd(
            host_name=vpn_server,
            command="cp /etc/wireguard/wg0.conf /etc/wireguard/wg0.conf.bak",
        )
        self.kathara_api.exec_cmd(
            host_name=vpn_server,
            command=f"sed -i '/# {target_host}/{{n; s/^/# /; n; s/^/# /; n; s/^/# /;}}' /etc/wireguard/wg0.conf",
        )
        self.kathara_api.exec_cmd(
            host_name=vpn_server,
            command="wg-quick down wg0 && wg-quick up wg0",
        )
        self.logger.info(f"Removed VPN membership of {target_host} on {vpn_server}.")

    def verify_fault(self, params: VPNMembershipMissingParams | None = None) -> dict:
        """Verify the VPN config for target_host has commented-out lines."""
        if params is None:
            params = VPNMembershipMissingParams()
        target_host = params.host_name if params.host_name is not None else self.target_host
        vpn_server = params.host_name_2 if params.host_name_2 is not None else self.vpn_server
        wg_conf_snippet = self.kathara_api.exec_cmd(
            host_name=vpn_server,
            command=f"grep -A4 '# {target_host}' /etc/wireguard/wg0.conf 2>/dev/null || echo absent",
        ).strip()
        lines = wg_conf_snippet.splitlines()
        commented_lines = [ln for ln in lines if ln.strip().startswith("#")]
        verified = len(commented_lines) >= 3
        return build_verify_result(
            root_cause_name=self.root_cause_name,
            faulty_devices=self.faulty_devices,
            verified=verified,
            details={
                "vpn_server": vpn_server,
                "target_host": target_host,
                "wg_conf_snippet": wg_conf_snippet,
            },
        )


class HostIncorrectDNSDetection(VPNMembershipMissingBase, DetectionTask):
    META = ProblemMeta(
        root_cause_category=VPNMembershipMissingBase.root_cause_category,
        root_cause_name=VPNMembershipMissingBase.root_cause_name,
        task_level=TaskLevel.DETECTION,
        description=TaskDescription.DETECTION,
    )


class HostIncorrectDNSLocalization(VPNMembershipMissingBase, LocalizationTask):
    META = ProblemMeta(
        root_cause_category=VPNMembershipMissingBase.root_cause_category,
        root_cause_name=VPNMembershipMissingBase.root_cause_name,
        task_level=TaskLevel.LOCALIZATION,
        description=TaskDescription.LOCALIZATION,
    )


class HostIncorrectDNSRCA(VPNMembershipMissingBase, RCATask):
    META = ProblemMeta(
        root_cause_category=VPNMembershipMissingBase.root_cause_category,
        root_cause_name=VPNMembershipMissingBase.root_cause_name,
        task_level=TaskLevel.RCA,
        description=TaskDescription.RCA,
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    host_ip_conflict = VPNMembershipMissingBase(scenario_name="rip_small_internet_vpn")
    host_ip_conflict.inject_fault()
