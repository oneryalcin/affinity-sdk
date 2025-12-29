from __future__ import annotations

from ..click_compat import RichCommand, click
from ..context import CLIContext
from ..options import output_options
from ..runner import CommandOutput, run_command
from ..serialization import serialize_model_for_cli


@click.command(name="whoami", cls=RichCommand)
@output_options
@click.pass_obj
def whoami_cmd(ctx: CLIContext) -> None:
    def fn(ctx: CLIContext, warnings: list[str]) -> CommandOutput:
        client = ctx.get_client(warnings=warnings)
        who = client.whoami()
        return CommandOutput(
            data=serialize_model_for_cli(who),
            warnings=warnings,
            api_called=True,
        )

    run_command(ctx, command="whoami", fn=fn)
