"""Execute one shell command inside a host of the selected running session."""

from nika.utils.session import Session


def exec_command_in_host(
    *,
    host: str,
    command: str,
    session_id: str | None = None,
    timeout: float = 10.0,
) -> str:
    """Run ``command`` on ``host`` within the lab bound to ``session_id``."""
    from nika.service.kathara.base_api import KatharaBaseAPI

    session = Session()
    session.load_running_session(session_id=session_id)
    kathara = KatharaBaseAPI(lab_name=session.lab_name)
    return kathara.exec_cmd(host_name=host, command=command, timeout=timeout)
