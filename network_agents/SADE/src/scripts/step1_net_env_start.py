import argparse
from typing import Literal

from nika.net_env.net_env_pool import get_net_env_instance
from nika.utils.logger import refresh_logger, system_logger
from nika.utils.session import Session


def start_net_env(scenario: str, topo_size: Literal["s", "m", "l"] | None = None, redeploy: bool = True):
    """
    Every run starts a new session.
    """
    refresh_logger()
    net_env = get_net_env_instance(scenario, topo_size=topo_size)
    if net_env.lab_exists() and redeploy:
        net_env.undeploy()
        net_env.deploy()
    elif not net_env.lab_exists():
        net_env.deploy()

    # save session data for follow-up steps
    session = Session()
    session.init_session()
    session.update_session("scenario_name", scenario)
    session.update_session("scenario_topo_size", topo_size)
    system_logger.info(f"Started network environment: {scenario} with size {topo_size} in session {session.session_id}")
    return net_env


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Start network environment with specified parameters (i.e., topology size)."
    )

    parser.add_argument(
        "--scenario",
        type=str,
        default="simple_bgp",
        help="Name of the network environment to start (default: simple_bgp)",
    )

    parser.add_argument(
        "--topo_size",
        type=str,
        choices=["s", "m", "l"],
        default=None,
        help="Topology size (s/m/l). Only required for certain scenarios.",
    )

    args = parser.parse_args()
    start_net_env(args.scenario, args.topo_size)
