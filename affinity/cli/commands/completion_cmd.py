from __future__ import annotations

import sys

from ..click_compat import RichCommand, click
from ..context import CLIContext
from ..decorators import category
from ..options import output_options
from ..runner import CommandOutput, run_command


@category("local")
@click.command(name="completion", cls=RichCommand)
@click.argument("shell", type=click.Choice(["bash", "zsh", "fish"]))
@output_options
@click.pass_obj
def completion_cmd(ctx: CLIContext, shell: str) -> None:
    """Output shell completion script for bash, zsh, or fish."""
    if shell == "bash":
        script = 'eval "$(_XAFFINITY_COMPLETE=bash_source xaffinity)"\n'
    elif shell == "zsh":
        script = 'eval "$(_XAFFINITY_COMPLETE=zsh_source xaffinity)"\n'
    else:
        script = "eval (env _XAFFINITY_COMPLETE=fish_source xaffinity)\n"

    if ctx.output == "table":
        sys.stdout.write(script)
        raise click.exceptions.Exit(0)

    def fn(_: CLIContext, _warnings: list[str]) -> CommandOutput:
        return CommandOutput(data={"shell": shell, "script": script}, api_called=False)

    run_command(ctx, command="completion", fn=fn)
