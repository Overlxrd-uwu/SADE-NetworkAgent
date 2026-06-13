"""Integration tests for verify_fault across dns/crash/vpn/service fault types.

Prerequisites:
  - Docker must be running
  - Run via: uv run python -m unittest tests/failure_inject_verify/test_end_host_dns_crash_verify.py -v
"""

import unittest

from nika.orchestrator.problems.end_host_failure.dns import DNSRecordErrorDetection
from nika.orchestrator.problems.end_host_failure.host_failure import HostCrashDetection, HostCrashParams
from nika.orchestrator.problems.end_host_failure.service_failure import (
    DHCPServiceDownDetection,
    DNSServiceDownDetection,
)
from nika.orchestrator.problems.end_host_failure.vpn import HostIncorrectDNSDetection as VPNMembershipMissingDetection
from tests.integration_base import FailureInjectVerifyTestCase


class DNSRecordErrorVerifyTest(FailureInjectVerifyTestCase):
    SCENARIO = "ospf_enterprise_dhcp"
    ENV_RUN_ARGS = ["-t", "s"]

    def test_dns_record_error_verify_true_after_inject(self):
        """verify_fault returns verified=True after DNS zone file is modified."""
        problem = self._problem(DNSRecordErrorDetection)
        problem.inject_fault()
        result = problem.verify_fault()
        self.assertTrue(result["verified"], f"Expected DNS record error to be verified: {result}")
        self.assertIn("found", result["details"]["grep_result"])
        self.assertTrue(result["details"]["file_has_wrong_ip"])
        self.assertTrue(result["details"]["dns_resolves_wrong"])


class HostCrashVerifyTest(FailureInjectVerifyTestCase):
    SCENARIO = "simple_bgp"
    HOST = "pc1"

    def test_host_crash_verify_true_after_inject(self):
        """verify_fault returns verified=True after host container is paused."""
        params = HostCrashParams(host_name=self.HOST)
        problem = self._problem(HostCrashDetection)
        problem.inject_fault(params)
        result = problem.verify_fault(params)
        self.assertTrue(result["verified"], f"Expected host crash to be verified: {result}")
        self.assertEqual(result["details"]["container_status"], "paused")


class VPNMembershipMissingVerifyTest(FailureInjectVerifyTestCase):
    SCENARIO = "rip_small_internet_vpn"
    ENV_RUN_ARGS = ["-t", "s"]

    def test_vpn_membership_missing_verify_true_after_inject(self):
        """verify_fault returns verified=True after VPN membership is commented out."""
        problem = self._problem(VPNMembershipMissingDetection)
        problem.inject_fault()
        result = problem.verify_fault()
        self.assertTrue(result["verified"], f"Expected VPN membership missing to be verified: {result}")


class ServiceDownVerifyTest(FailureInjectVerifyTestCase):
    """Tests for DNS/DHCP service down via pkill -9 (works in Kathara without systemd)."""

    SCENARIO = "ospf_enterprise_dhcp"
    ENV_RUN_ARGS = ["-t", "s"]

    def test_dns_service_down_verify_true_after_inject(self):
        """verify_fault returns verified=True after named process is killed with pkill -9."""
        problem = self._problem(DNSServiceDownDetection)
        problem.inject_fault()
        result = problem.verify_fault()
        self.assertTrue(result["verified"], f"Expected DNS service to be down: {result}")

    def test_dhcp_service_down_verify_true_after_inject(self):
        """verify_fault returns verified=True after dhcpd process is killed with pkill -9."""
        problem = self._problem(DHCPServiceDownDetection)
        problem.inject_fault()
        result = problem.verify_fault()
        self.assertTrue(result["verified"], f"Expected DHCP service to be down: {result}")


if __name__ == "__main__":
    unittest.main()
