from __future__ import annotations

from affinity.models.secondary import MergeTask

from ..click_compat import RichCommand, RichGroup, click
from ..context import CLIContext
from ..options import output_options
from ..runner import CommandOutput, run_command
from ..serialization import serialize_model_for_cli


@click.group(name="task", cls=RichGroup)
def task_group() -> None:
    """Task commands."""


def _task_payload(task: MergeTask) -> dict[str, object]:
    return serialize_model_for_cli(task)


@task_group.command(name="get", cls=RichCommand)
@click.argument("task_url")
@output_options
@click.pass_obj
def task_get(ctx: CLIContext, task_url: str) -> None:
    """Get task status."""

    def fn(ctx: CLIContext, warnings: list[str]) -> CommandOutput:
        client = ctx.get_client(warnings=warnings)
        task = client.tasks.get(task_url)
        payload = _task_payload(task)
        return CommandOutput(data={"task": payload}, api_called=True)

    run_command(ctx, command="task get", fn=fn)


@task_group.command(name="wait", cls=RichCommand)
@click.argument("task_url")
@click.option("--timeout", type=float, default=300.0, show_default=True)
@click.option("--poll-interval", type=float, default=2.0, show_default=True)
@click.option("--max-poll-interval", type=float, default=30.0, show_default=True)
@output_options
@click.pass_obj
def task_wait(
    ctx: CLIContext,
    task_url: str,
    *,
    timeout: float,
    poll_interval: float,
    max_poll_interval: float,
) -> None:
    """Wait for a task to complete."""

    def fn(ctx: CLIContext, warnings: list[str]) -> CommandOutput:
        client = ctx.get_client(warnings=warnings)
        task = client.tasks.wait(
            task_url,
            timeout=timeout,
            poll_interval=poll_interval,
            max_poll_interval=max_poll_interval,
        )
        payload = _task_payload(task)
        return CommandOutput(data={"task": payload}, api_called=True)

    run_command(ctx, command="task wait", fn=fn)
