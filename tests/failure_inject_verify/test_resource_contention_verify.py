"""Integration tests for verify_fault across resource-contention fault types.

Prerequisites:
  - Docker must be running
  - Run via: uv run python -m unittest tests/failure_inject_verify/test_resource_contention_verify.py -v
"""

import unittest

from nika.orchestrator.problems.resource_contention.link_issue import (
    IncastTrafficNetworkLimitationDetection,
    LinkBandwidthThrottlingDetection,
    LinkBandwidthThrottlingParams,
    LinkHighPacketCorruptionDetection,
    LinkHighPacketCorruptionParams,
)
from nika.orchestrator.problems.resource_contention.service_issue import (
    DNSLookupLatencyDetection,
    DNSLookupLatencyParams,
    LoadBalancerOverloadDetection,
)
from nika.orchestrator.problems.resource_contention.tcp_issue import (
    ReceiverResourceContentionDetection,
    SenderResourceContentionDetection,
)
from tests.integration_base import FailureInjectVerifyTestCase


class StressVerifyTest(FailureInjectVerifyTestCase):
    """Tests for stress-ng based faults."""

    SCENARIO = "ospf_enterprise_dhcp"
    ENV_RUN_ARGS = ["-t", "s"]

    def test_sender_resource_contention_verify(self):
        """verify_fault returns verified=True after stress-ng is injected on the sender."""
        problem = self._problem(SenderResourceContentionDetection)
        problem.inject_fault()
        result = problem.verify_fault()
        self.assertTrue(result["verified"], f"Expected stress-ng running: {result}")

    def test_receiver_resource_contention_verify(self):
        """verify_fault returns verified=True after stress-ng is injected on the receiver."""
        problem = self._problem(ReceiverResourceContentionDetection)
        problem.inject_fault()
        result = problem.verify_fault()
        self.assertTrue(result["verified"], f"Expected stress-ng running: {result}")

    def test_load_balancer_overload_verify(self):
        """verify_fault returns verified=True after stress-ng is injected on the load balancer."""
        problem = self._problem(LoadBalancerOverloadDetection)
        problem.inject_fault()
        result = problem.verify_fault()
        self.assertTrue(result["verified"], f"Expected stress-ng running: {result}")


class DNSLookupLatencyVerifyTest(FailureInjectVerifyTestCase):
    SCENARIO = "dc_clos_service"
    ENV_RUN_ARGS = ["-t", "s"]

    def test_dns_lookup_latency_verify_true_after_inject(self):
        """verify_fault returns verified=True after tc delay is injected on DNS server."""
        params = DNSLookupLatencyParams(intf_name="eth0", delay_ms=500)
        problem = self._problem(DNSLookupLatencyDetection)
        problem.inject_fault(params)
        result = problem.verify_fault(params)
        self.assertTrue(result["verified"], f"Expected tc delay to be present: {result}")
        self.assertIn("delay", result["details"]["tc_output"])


class LinkIssueVerifyTest(FailureInjectVerifyTestCase):
    SCENARIO = "simple_bgp"

    def test_link_high_packet_corruption_verify_true_after_inject(self):
        """verify_fault returns verified=True after corruption rule is injected."""
        params = LinkHighPacketCorruptionParams(host_name="pc1", corruption_percentage=60)
        problem = self._problem(LinkHighPacketCorruptionDetection)
        problem.inject_fault(params)
        result = problem.verify_fault(params)
        self.assertTrue(result["verified"], f"Expected corrupt qdisc: {result}")
        self.assertIn("corrupt", result["details"]["tc_output"])

    def test_link_bandwidth_throttling_verify_true_after_inject(self):
        """verify_fault returns verified=True after TBF qdisc is injected."""
        params = LinkBandwidthThrottlingParams(host_name="pc1")
        problem = self._problem(LinkBandwidthThrottlingDetection)
        problem.inject_fault(params)
        result = problem.verify_fault(params)
        self.assertTrue(result["verified"], f"Expected tbf qdisc: {result}")
        self.assertIn("tbf", result["details"]["tc_output"])


class IncastTrafficLimitationVerifyTest(FailureInjectVerifyTestCase):
    """Incast limitation targets web servers; requires dc_clos_service, not simple_bgp."""

    SCENARIO = "dc_clos_service"
    ENV_RUN_ARGS = ["-t", "s"]

    def test_incast_traffic_limitation_verify_true_after_inject(self):
        """verify_fault returns verified=True after netem/tbf is injected on web server."""
        problem = self._problem(IncastTrafficNetworkLimitationDetection)
        problem.inject_fault()
        result = problem.verify_fault()
        self.assertTrue(result["verified"], f"Expected netem/tbf qdisc: {result}")
        self.assertIn("netem", result["details"]["tc_output"])
        self.assertIn("tbf", result["details"]["tc_output"])


if __name__ == "__main__":
    unittest.main()
