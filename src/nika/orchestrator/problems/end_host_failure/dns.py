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
from nika.service.kathara import KatharaBaseAPI
from nika.utils.logger import system_logger

logger = system_logger

# ==================================================================
# Problem: DNS record error. Apps resolve domain but connect to wrong host.
# ==================================================================


class DNSRecordErrorParams(BaseModel):
    """Parameters for injecting a DNS record error fault."""

    host_name: Optional[str] = Field(default=None, description="Target DNS server host name. Defaults to runtime selection.")
    target_website: Optional[str] = Field(default=None, description="Record host label.")
    target_domain: Optional[str] = Field(default=None, description="DNS zone/domain.")
    wrong_ip: Optional[str] = Field(default=None, description="Incorrect IP to set.")


class DNSRecordErrorBase:
    root_cause_category: RootCauseCategory = RootCauseCategory.END_HOST_FAILURE
    root_cause_name: str = "dns_record_error"

    symptom_desc = "Some hosts cannot access external websites."
    TAGS: str = ["dns"]

    Params = DNSRecordErrorParams

    def __init__(self, scenario_name: str | None, **kwargs):
        super().__init__()
        self.net_env = get_net_env_instance(scenario_name, **kwargs)
        self.kathara_api = KatharaBaseAPI(lab_name=self.net_env.lab.name)
        self.injector = FaultInjectorBase(lab_name=self.net_env.lab.name)
        self.faulty_devices = [self.net_env.servers["dns"][0]]
        url = random.choice(self.net_env.web_urls)

        self.target_website = url.split(".")[0]

        if self.target_website.startswith("http://"):
            self.target_website = self.target_website[len("http://"):]

        self.target_domain = url.split(".")[1]
        self.right_ip = self.kathara_api.get_host_ip(self.faulty_devices[0])
        self.wrong_ip = self.kathara_api.get_host_ip(self.net_env.hosts[0])

    def inject_fault(self, params: DNSRecordErrorParams | None = None):
        if params is None:
            params = DNSRecordErrorParams()
        host = params.host_name if params.host_name is not None else self.faulty_devices[0]
        target_website = params.target_website if params.target_website is not None else self.target_website
        target_domain = params.target_domain if params.target_domain is not None else self.target_domain
        wrong_ip = params.wrong_ip if params.wrong_ip is not None else self.wrong_ip

        self.kathara_api.exec_cmd(
            host,
            f"cp /etc/bind/db.{target_domain} /etc/bind/db.{target_domain}.bak",
        )
        cmd = r"sed -i 's/^\({name}[[:space:]]\+IN[[:space:]]\+A[[:space:]]\+\)[0-9\.]\+/\1{new_ip}/' /etc/bind/db.{domain}"
        cmd = cmd.format(name=target_website, new_ip=wrong_ip, domain=target_domain)
        self.kathara_api.exec_cmd(host, cmd)
        self.kathara_api.exec_cmd(host, "systemctl restart named")
        logger.info(
            f"Injecting DNS record error on {host}: mapping {target_website}:{target_domain} "
            f"to wrong IP {wrong_ip} instead of {self.right_ip}"
        )


class DNSRecordErrorDetection(DNSRecordErrorBase, DetectionTask):
    META = ProblemMeta(
        root_cause_category=DNSRecordErrorBase.root_cause_category,
        root_cause_name=DNSRecordErrorBase.root_cause_name,
        task_level=TaskLevel.DETECTION,
        description=TaskDescription.DETECTION,
    )


class DNSRecordErrorLocalization(DNSRecordErrorBase, LocalizationTask):
    META = ProblemMeta(
        root_cause_category=DNSRecordErrorBase.root_cause_category,
        root_cause_name=DNSRecordErrorBase.root_cause_name,
        task_level=TaskLevel.LOCALIZATION,
        description=TaskDescription.LOCALIZATION,
    )


class DNSRecordErrorRCA(DNSRecordErrorBase, RCATask):
    META = ProblemMeta(
        root_cause_category=DNSRecordErrorBase.root_cause_category,
        root_cause_name=DNSRecordErrorBase.root_cause_name,
        task_level=TaskLevel.RCA,
        description=TaskDescription.RCA,
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    dns_error = DNSRecordErrorBase(scenario_name="ospf_enterprise_dhcp")
    dns_error.inject_fault()
