"""Root Typer application for the `nika` console script."""

import typer

from nika.cli.commands.agent import agent_app
from nika.cli.commands.benchmark import benchmark_app
from nika.cli.commands.env import env_app
from nika.cli.commands.evaluation import eval_app
from nika.cli.commands.exec import exec_command
from nika.cli.commands.failure import failure_app
from nika.cli.commands.session import session_app
from nika.cli.commands.traffic import traffic_app

app = typer.Typer(help="NIKA network troubleshooting pipeline CLI.")
app.add_typer(session_app, name="session")
app.add_typer(env_app, name="env")
app.add_typer(failure_app, name="failure")
app.command("exec", context_settings={"allow_interspersed_args": False})(exec_command)
app.add_typer(agent_app, name="agent")
app.add_typer(eval_app, name="eval")
app.add_typer(benchmark_app, name="benchmark")
app.add_typer(traffic_app, name="traffic")


def main() -> None:
    """Console entrypoint for setuptools `[project.scripts]`."""
    app()


if __name__ == "__main__":
    main()
