"""Commands for running diagnosis agents."""

import typer

SUPPORTED_AGENT_TYPES = ("react", "mock")
SUPPORTED_LLM_BACKENDS = ("openai", "ollama", "deepseek")

agent_app = typer.Typer(help="Troubleshooting agents.")


@agent_app.command("list")
def agent_list() -> None:
    """Print supported agent types and LLM backends."""
    typer.echo("agent_types:")
    for agent_type in SUPPORTED_AGENT_TYPES:
        typer.echo(f"  {agent_type}")
    typer.echo("llm_backends:")
    for backend in SUPPORTED_LLM_BACKENDS:
        typer.echo(f"  {backend}")


@agent_app.command("run")
def agent_run(
    agent_type: str = typer.Option("react", "-a", "--agent", help="Agent implementation."),
    llm_backend: str = typer.Option("openai", "-b", "--backend", help="LLM provider (openai, ollama, deepseek)."),
    model: str = typer.Option("gpt-5-mini", "-m", "--model", help="Model id for the chosen backend."),
    max_steps: int = typer.Option(20, "-n", "--max-steps", help="Max ReAct steps."),
    session_id: str | None = typer.Option(None, "--session-id", help="Target session id (lab_hash)."),
) -> None:
    """Run the agent on the current session task."""
    from nika.workflows.agent_run import start_agent

    try:
        start_agent(agent_type, llm_backend, model, max_steps, session_id=session_id)
    except (FileNotFoundError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
