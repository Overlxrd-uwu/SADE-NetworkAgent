"""Integration tests for verify_fault across network-attack fault types.

Prerequisites:
  - Docker must be running
  - Run via: uv run python -m unittest tests/failure_inject_verify/test_network_attack_verify.py -v
"""

import unittest

from nika.orchestrator.problems.network_under_attack.arp import ArpCachePoisoningDetection, ArpCachePoisoningParams
from nika.orchestrator.problems.network_under_attack.bgp import BGPHijackingDetection
from nika.orchestrator.problems.network_under_attack.dhcp import (
    DHCPSpoofedDNSDetection,
    DHCPSpoofedGatewayDetection,
    DHCPSpoofedSubnetDetection,
)
from nika.orchestrator.problems.network_under_attack.web import WebDoSDetection
from tests.integration_base import FailureInjectVerifyTestCase


class WebDoSVerifyTest(FailureInjectVerifyTestCase):
    SCENARIO = "dc_clos_service"
    ENV_RUN_ARGS = ["-t", "s"]

    def test_web_dos_verify_true_after_inject(self):
        """verify_fault returns verified=True after ab DoS attack is injected."""
        problem = self._problem(WebDoSDetection)
        problem.inject_fault()
        result = problem.verify_fault()
        self.assertTrue(result["verified"], f"Expected ab attack running: {result}")


class DHCPAttackVerifyTest(FailureInjectVerifyTestCase):
    SCENARIO = "ospf_enterprise_dhcp"
    ENV_RUN_ARGS = ["-t", "s"]

    def test_dhcp_spoofed_gateway_verify(self):
        """verify_fault returns verified=True after spoofed gateway is written to dhcpd.conf."""
        problem = self._problem(DHCPSpoofedGatewayDetection)
        problem.inject_fault()
        result = problem.verify_fault()
        self.assertTrue(result["verified"], f"Expected spoofed gateway: {result}")

    def test_dhcp_spoofed_dns_verify(self):
        """verify_fault returns verified=True after spoofed DNS is written to dhcpd.conf."""
        problem = self._problem(DHCPSpoofedDNSDetection)
        problem.inject_fault()
        result = problem.verify_fault()
        self.assertTrue(result["verified"], f"Expected spoofed DNS: {result}")

    def test_dhcp_spoofed_subnet_verify(self):
        """verify_fault returns verified=True after subnet is deleted from dhcpd.conf."""
        problem = self._problem(DHCPSpoofedSubnetDetection)
        problem.inject_fault()
        result = problem.verify_fault()
        self.assertTrue(result["verified"], f"Expected subnet deleted: {result}")


class BGPHijackingVerifyTest(FailureInjectVerifyTestCase):
    SCENARIO = "simple_bgp"

    def test_bgp_hijacking_verify_true_after_inject(self):
        """verify_fault returns verified=True after BGP hijacking is injected."""
        problem = self._problem(BGPHijackingDetection)
        problem.inject_fault()
        result = problem.verify_fault()
        self.assertTrue(result["verified"], f"Expected BGP hijacking to be verified: {result}")
        self.assertTrue(result["details"]["has_advertisement"])

    def test_arp_cache_poisoning_verify_true_after_inject(self):
        """verify_fault returns verified=True after ARP cache is poisoned."""
        params = ArpCachePoisoningParams(host_name="pc1", fake_mac="00:11:22:33:44:55")
        problem = self._problem(ArpCachePoisoningDetection)
        problem.inject_fault(params)
        result = problem.verify_fault(params)
        self.assertTrue(result["verified"], f"Expected ARP poisoning to be verified: {result}")
        self.assertIn("00:11:22:33:44:55", result["details"]["neigh_entry"])


if __name__ == "__main__":
    unittest.main()
