from __future__ import annotations

from pathlib import Path
from typing import Literal

import affinity

from .click_compat import RichGroup, click
from .context import CLIContext
from .logging import configure_logging, restore_logging
from .paths import get_paths


@click.group(
    name="affinity",
    invoke_without_command=True,
    context_settings={"help_option_names": ["-h", "--help"]},
    cls=RichGroup,
)
@click.option(
    "--output",
    type=click.Choice(["table", "json"]),
    default="table",
)
@click.option("--json", "json_flag", is_flag=True, help="Alias for --output json.")
@click.option("-q", "--quiet", is_flag=True, help="Suppress non-essential stderr output.")
@click.option("-v", "verbose", count=True, help="Increase verbosity (-v, -vv).")
@click.option("--pager/--no-pager", default=None, help="Page table / long output when interactive.")
@click.option(
    "--progress/--no-progress",
    default=None,
    help="Force enable/disable progress bars (stderr).",
)
@click.option("--profile", type=str, default=None, help="Config profile name.")
@click.option("--dotenv/--no-dotenv", default=False, help="Opt-in .env loading.")
@click.option(
    "--env-file",
    type=click.Path(dir_okay=False),
    default=".env",
)
@click.option(
    "--api-key-file",
    type=str,
    default=None,
    help="Read API key from file (or '-' for stdin).",
)
@click.option("--api-key-stdin", is_flag=True, help="Alias for --api-key-file -.")
@click.option("--timeout", type=float, default=None, help="Per-request timeout in seconds.")
@click.option(
    "--max-retries",
    type=int,
    default=3,
    show_default=True,
    help="Maximum retries for rate-limited requests.",
)
@click.option(
    "--beta",
    is_flag=True,
    help="Enable beta endpoints (required for merge commands).",
)
@click.option(
    "--readonly",
    is_flag=True,
    help="Disallow write operations (safety guard; affects all SDK calls).",
)
@click.option(
    "--trace",
    is_flag=True,
    help="Trace request/response/error events to stderr (safe redaction).",
)
@click.option("--log-file", type=click.Path(dir_okay=False), default=None)
@click.option("--no-log-file", is_flag=True, help="Disable file logging explicitly.")
@click.option("--v1-base-url", type=str, default=None, help="Override v1 base URL.")
@click.option("--v2-base-url", type=str, default=None, help="Override v2 base URL.")
@click.version_option(version=affinity.__version__, prog_name="affinity")
@click.pass_context
def cli(
    click_ctx: click.Context,
    *,
    output: str,
    json_flag: bool,
    quiet: bool,
    verbose: int,
    pager: bool | None,
    progress: bool | None,
    profile: str | None,
    dotenv: bool,
    env_file: str,
    api_key_file: str | None,
    api_key_stdin: bool,
    timeout: float | None,
    max_retries: int,
    beta: bool,
    readonly: bool,
    trace: bool,
    log_file: str | None,
    no_log_file: bool,
    v1_base_url: str | None,
    v2_base_url: str | None,
) -> None:
    if click_ctx.invoked_subcommand is None:
        # No args: show help; no network calls.
        click.echo(click_ctx.get_help())
        raise click.exceptions.Exit(0)

    out = "json" if json_flag else output
    progress_mode: Literal["auto", "always", "never"] = "auto"
    if progress is True:
        progress_mode = "always"
    if progress is False:
        progress_mode = "never"
    if trace and progress is None:
        progress_mode = "never"

    paths = get_paths()
    effective_log_file = Path(log_file) if log_file else paths.log_file
    enable_log_file = not no_log_file

    click_ctx.obj = CLIContext(
        output=out,  # type: ignore[arg-type]
        quiet=quiet,
        verbosity=verbose,
        pager=pager,
        progress=progress_mode,
        profile=profile,
        dotenv=dotenv,
        env_file=Path(env_file),
        api_key_file=api_key_file,
        api_key_stdin=api_key_stdin,
        timeout=timeout,
        max_retries=max_retries,
        enable_beta_endpoints=beta,
        readonly=readonly,
        trace=trace,
        log_file=effective_log_file,
        enable_log_file=enable_log_file,
        v1_base_url=v1_base_url,
        v2_base_url=v2_base_url,
        _paths=paths,
    )

    click_ctx.call_on_close(click_ctx.obj.close)

    previous_logging = configure_logging(
        verbosity=verbose,
        log_file=effective_log_file,
        enable_file=enable_log_file,
        api_key_for_redaction=None,
    )
    click_ctx.call_on_close(lambda: restore_logging(previous_logging))


# Register commands
from .commands.company_cmds import company_group as _company_group  # noqa: E402
from .commands.completion_cmd import completion_cmd as _completion_cmd  # noqa: E402
from .commands.config_cmds import config_group as _config_group  # noqa: E402
from .commands.field_cmds import field_group as _field_group  # noqa: E402
from .commands.field_value_changes_cmds import (  # noqa: E402
    field_value_changes_group as _field_value_changes_group,
)
from .commands.field_value_cmds import field_value_group as _field_value_group  # noqa: E402
from .commands.interaction_cmds import interaction_group as _interaction_group  # noqa: E402
from .commands.list_cmds import list_group as _list_group  # noqa: E402
from .commands.note_cmds import note_group as _note_group  # noqa: E402
from .commands.opportunity_cmds import opportunity_group as _opportunity_group  # noqa: E402
from .commands.person_cmds import person_group as _person_group  # noqa: E402
from .commands.relationship_strength_cmds import (  # noqa: E402
    relationship_strength_group as _relationship_strength_group,
)
from .commands.reminder_cmds import reminder_group as _reminder_group  # noqa: E402
from .commands.resolve_url_cmd import resolve_url_cmd as _resolve_url_cmd  # noqa: E402
from .commands.task_cmds import task_group as _task_group  # noqa: E402
from .commands.version_cmd import version_cmd as _version_cmd  # noqa: E402
from .commands.whoami_cmd import whoami_cmd as _whoami_cmd  # noqa: E402

cli.add_command(_completion_cmd)
cli.add_command(_version_cmd)
cli.add_command(_config_group)
cli.add_command(_whoami_cmd)
cli.add_command(_resolve_url_cmd)
cli.add_command(_person_group)
cli.add_command(_company_group)
cli.add_command(_opportunity_group)
cli.add_command(_list_group)
cli.add_command(_note_group)
cli.add_command(_reminder_group)
cli.add_command(_interaction_group)
cli.add_command(_field_group)
cli.add_command(_field_value_group)
cli.add_command(_field_value_changes_group)
cli.add_command(_relationship_strength_group)
cli.add_command(_task_group)
