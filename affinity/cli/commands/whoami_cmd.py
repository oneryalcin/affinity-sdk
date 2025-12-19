from __future__ import annotations

import click

from ..click_compat import RichCommand
from ..context import CLIContext
from ..options import output_options
from ..runner import CommandOutput, run_command


@click.command(name="whoami", cls=RichCommand)
@output_options
@click.pass_obj
def whoami_cmd(ctx: CLIContext) -> None:
    def fn(ctx: CLIContext, warnings: list[str]) -> CommandOutput:
        client = ctx.get_client(warnings=warnings)
        who = client.whoami()
        return CommandOutput(
            data=who.model_dump(by_alias=True, mode="json"),
            warnings=warnings,
            api_called=True,
        )

    run_command(ctx, command="whoami", fn=fn)
