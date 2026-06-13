"""Integration tests for verify_fault across misconfiguration fault types.

Prerequisites:
  - Docker must be running
  - Run via: uv run python -m unittest tests/failure_inject_verify/test_misconfig_verify.py -v
"""

import unittest

from nika.orchestrator.problems.misconfigurations.acl_error import (
    ARPAclBlockDetection,
    BGPAclBlockDetection,
    HttpAclBlockDetection,
    IcmpAclBlockDetection,
)
from nika.orchestrator.problems.misconfigurations.bgp import (
    BGPAsnMisconfigDetection,
    BGPBlackholeRouteLeakDetection,
    BGPHijackingDetection,
    BGPMissingAdvertiseDetection,
    StaticBlackHoleDetection,
)
from nika.orchestrator.problems.misconfigurations.dhcp import DHCPMissingSubnetDetection
from nika.orchestrator.problems.misconfigurations.mac import MacAddressConflictDetection
from nika.orchestrator.problems.misconfigurations.ospf import (
    OSPFAreaMisconfigDetection,
    OSPFNeighborMissingDetection,
)
from nika.orchestrator.problems.misconfigurations.p4 import (
    P4AggressiveDetectionThresholdsDetection,
)
from tests.integration_base import FailureInjectVerifyTestCase


class OSPFMisconfigVerifyTest(FailureInjectVerifyTestCase):
    SCENARIO = "ospf_enterprise_static"
    ENV_RUN_ARGS = ["-t", "s"]

    def test_ospf_area_misconfig_verify(self):
        """verify_fault returns verified=True when file area differs from in-memory area after inject."""
        problem = self._problem(OSPFAreaMisconfigDetection)
        problem.inject_fault()
        result = problem.verify_fault()
        self.assertTrue(result["verified"], f"Expected OSPF area misconfig: {result}")

    def test_ospf_neighbor_missing_verify_file_updated(self):
        """verify_fault checks frr.conf file has commented network lines (not in-memory)."""
        problem = self._problem(OSPFNeighborMissingDetection)
        problem.inject_fault()
        result = problem.verify_fault()
        self.assertTrue(result["verified"], f"Expected OSPF neighbor missing (file): {result}")
        self.assertGreater(result["details"]["commented_network_count"], 0)


class BGPMisconfigVerifyTest(FailureInjectVerifyTestCase):
    SCENARIO = "simple_bgp"

    def test_bgp_asn_misconfig_verify(self):
        """verify_fault returns verified=True when file ASN differs from in-memory ASN after inject."""
        problem = self._problem(BGPAsnMisconfigDetection)
        problem.inject_fault()
        result = problem.verify_fault()
        self.assertTrue(result["verified"], f"Expected BGP ASN misconfig: {result}")

    def test_bgp_missing_advertise_verify(self):
        """verify_fault returns verified=True after network lines are commented out in frr.conf."""
        problem = self._problem(BGPMissingAdvertiseDetection)
        problem.inject_fault()
        result = problem.verify_fault()
        self.assertTrue(result["verified"], f"Expected BGP missing advertise: {result}")

    def test_static_blackhole_verify_true_after_inject(self):
        """verify_fault returns verified=True after blackhole route is injected."""
        problem = self._problem(StaticBlackHoleDetection)
        problem.inject_fault()
        result = problem.verify_fault()
        self.assertTrue(result["verified"], f"Expected blackhole route: {result}")
        self.assertIn("blackhole", result["details"]["route_output"])

    def test_bgp_blackhole_route_leak_verify(self):
        """verify_fault returns verified=True after Null0 route is added."""
        problem = self._problem(BGPBlackholeRouteLeakDetection)
        problem.inject_fault()
        result = problem.verify_fault()
        self.assertTrue(result["verified"], f"Expected Null0 route: {result}")

    def test_bgp_hijacking_verify_true_after_inject(self):
        """verify_fault returns verified=True after BGP hijacking advertisement is added."""
        problem = self._problem(BGPHijackingDetection)
        problem.inject_fault()
        result = problem.verify_fault()
        self.assertTrue(result["verified"], f"Expected BGP hijacking: {result}")


class MacMisconfigVerifyTest(FailureInjectVerifyTestCase):
    SCENARIO = "ospf_enterprise_static"
    ENV_RUN_ARGS = ["-t", "s"]

    def test_mac_address_conflict_verify_true_after_inject(self):
        """verify_fault returns verified=True after MAC address conflict is injected."""
        problem = self._problem(MacAddressConflictDetection)
        problem.inject_fault()
        result = problem.verify_fault()
        self.assertTrue(result["verified"], f"Expected MAC conflict: {result}")
        self.assertEqual(result["details"]["mac_0"].lower(), result["details"]["mac_1"].lower())


class DHCPMisconfigVerifyTest(FailureInjectVerifyTestCase):
    SCENARIO = "ospf_enterprise_dhcp"
    ENV_RUN_ARGS = ["-t", "s"]

    def test_dhcp_missing_subnet_verify_true_after_inject(self):
        """verify_fault returns verified=True after DHCP subnet is deleted."""
        problem = self._problem(DHCPMissingSubnetDetection)
        problem.inject_fault()
        result = problem.verify_fault()
        self.assertTrue(result["verified"], f"Expected DHCP missing subnet: {result}")
        self.assertIn("absent", result["details"]["grep_result"])


class ACLBlockVerifyTest(FailureInjectVerifyTestCase):
    SCENARIO = "simple_bgp"

    def test_bgp_acl_block_verify_true_after_inject(self):
        """verify_fault returns verified=True after BGP ACL block is injected."""
        problem = self._problem(BGPAclBlockDetection)
        problem.inject_fault()
        result = problem.verify_fault()
        self.assertTrue(result["verified"], f"Expected BGP ACL block: {result}")

    def test_icmp_acl_block_verify_true_after_inject(self):
        """verify_fault returns verified=True after ICMP ACL block is injected."""
        problem = self._problem(IcmpAclBlockDetection)
        problem.inject_fault()
        result = problem.verify_fault()
        self.assertTrue(result["verified"], f"Expected ICMP ACL block: {result}")

    def test_http_acl_block_verify_true_after_inject(self):
        """verify_fault returns verified=True after HTTP ACL block is injected."""
        problem = self._problem(HttpAclBlockDetection)
        problem.inject_fault()
        result = problem.verify_fault()
        self.assertTrue(result["verified"], f"Expected HTTP ACL block: {result}")

    def test_arp_acl_block_verify_true_after_inject(self):
        """verify_fault returns verified=True after ARP ACL block is injected."""
        problem = self._problem(ARPAclBlockDetection)
        problem.inject_fault()
        result = problem.verify_fault()
        self.assertTrue(result["verified"], f"Expected ARP ACL block: {result}")


class P4MisconfigVerifyTest(FailureInjectVerifyTestCase):
    SCENARIO = "p4_bloom_filter"

    def test_p4_aggressive_detection_thresholds_verify_true_after_inject(self):
        """verify_fault returns verified=True after PACKET_THRESHOLD is reduced."""
        problem = self._problem(P4AggressiveDetectionThresholdsDetection)
        problem.inject_fault()
        result = problem.verify_fault()
        self.assertTrue(result["verified"], f"Expected P4 threshold modified: {result}")
        self.assertTrue(result["details"]["threshold_modified"])


if __name__ == "__main__":
    unittest.main()
