from __future__ import annotations

import platform

import affinity

from ..click_compat import RichCommand, click
from ..context import CLIContext
from ..decorators import category
from ..options import output_options
from ..runner import CommandOutput, run_command


@category("local")
@click.command(name="version", cls=RichCommand)
@output_options
@click.pass_obj
def version_cmd(ctx: CLIContext) -> None:
    """Show version, Python, and platform information."""

    def fn(_: CLIContext, _warnings: list[str]) -> CommandOutput:
        data = {
            "version": affinity.__version__,
            "pythonVersion": platform.python_version(),
            "platform": platform.platform(),
        }
        return CommandOutput(data=data, api_called=False)

    run_command(ctx, command="version", fn=fn)
