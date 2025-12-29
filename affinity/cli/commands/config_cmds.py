from __future__ import annotations

import os
from contextlib import suppress

from ..click_compat import RichCommand, RichGroup, click
from ..config import config_init_template
from ..context import CLIContext
from ..errors import CLIError
from ..options import output_options
from ..runner import CommandOutput, run_command


@click.group(name="config", cls=RichGroup)
def config_group() -> None:
    """Configuration and profiles."""


@config_group.command(name="path", cls=RichCommand)
@output_options
@click.pass_obj
def config_path(ctx: CLIContext) -> None:
    """Show the path to the configuration file."""

    def fn(_: CLIContext, _warnings: list[str]) -> CommandOutput:
        path = ctx.paths.config_path
        return CommandOutput(data={"path": str(path), "exists": path.exists()}, api_called=False)

    run_command(ctx, command="config path", fn=fn)


@config_group.command(name="init", cls=RichCommand)
@click.option("--force", is_flag=True, help="Overwrite existing config file.")
@output_options
@click.pass_obj
def config_init(ctx: CLIContext, *, force: bool) -> None:
    """Create a new configuration file with template."""

    def fn(_: CLIContext, _warnings: list[str]) -> CommandOutput:
        path = ctx.paths.config_path
        path.parent.mkdir(parents=True, exist_ok=True)
        overwritten = False
        if path.exists():
            if not force:
                raise CLIError(
                    f"Config already exists: {path} (use --force to overwrite)",
                    exit_code=2,
                    error_type="usage_error",
                )
            overwritten = True

        path.write_text(config_init_template(), encoding="utf-8")
        if os.name == "posix":
            with suppress(OSError):
                path.chmod(0o600)
        return CommandOutput(
            data={"path": str(path), "created": True, "overwritten": overwritten},
            api_called=False,
        )

    run_command(ctx, command="config init", fn=fn)
