from __future__ import annotations

import platform

import click
import rich_click

import affinity

from ..context import CLIContext
from ..options import output_options
from ..runner import CommandOutput, run_command


@click.command(name="version", cls=rich_click.RichCommand)
@output_options
@click.pass_obj
def version_cmd(ctx: CLIContext) -> None:
    def fn(_: CLIContext, _warnings: list[str]) -> CommandOutput:
        data = {
            "version": affinity.__version__,
            "pythonVersion": platform.python_version(),
            "platform": platform.platform(),
        }
        return CommandOutput(data=data, api_called=False)

    run_command(ctx, command="version", fn=fn)
