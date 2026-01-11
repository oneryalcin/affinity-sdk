from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import affinity

from .click_compat import RichGroup, click
from .context import CLIContext
from .logging import configure_logging, restore_logging
from .paths import get_paths

if TYPE_CHECKING:
    pass


class _RootGroupMixin:
    """Mixin that adds --help --json support to the root CLI group."""

    def format_help(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        """Override to support --help --json for machine-readable output."""
        # Check if --json flag is present in args
        if "--json" in sys.argv:
            from .help_json import emit_help_json_and_exit

            emit_help_json_and_exit(ctx)

        # Standard help output
        super().format_help(ctx, formatter)  # type: ignore[misc]

    def main(self, *args: Any, **kwargs: Any) -> Any:
        """Override main to handle --help --json before Click processes args."""
        # Check for --help --json combination early
        argv = sys.argv[1:]
        if ("--help" in argv or "-h" in argv) and "--json" in argv:
            # Create a minimal context and emit JSON help
            with self.make_context("xaffinity", []) as ctx:  # type: ignore[attr-defined]
                from .help_json import emit_help_json_and_exit

                emit_help_json_and_exit(ctx)

        return super().main(*args, **kwargs)  # type: ignore[misc]


# Create RootGroup by mixing in the JSON help behavior with RichGroup
# This approach satisfies mypy since the base class is determined at import time
RootGroup: type[click.Group] = type("RootGroup", (_RootGroupMixin, RichGroup), {})


@click.group(
    name="xaffinity",
    invoke_without_command=True,
    cls=RootGroup,
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.option(
    "--output",
    type=click.Choice(["table", "json"]),
    default="table",
    help="Output format (table or json).",
)
@click.option("--json", "json_flag", is_flag=True, help="Alias for --output json.")
@click.option("-q", "--quiet", is_flag=True, help="Suppress non-essential stderr output.")
@click.option("-v", "verbose", count=True, help="Increase verbosity (-v, -vv).")
@click.option("--pager/--no-pager", default=None, help="Page table / long output when interactive.")
@click.option(
    "--all-columns",
    is_flag=True,
    help="Show all table columns (disable auto-limiting based on terminal width).",
)
@click.option(
    "--max-columns",
    type=int,
    default=None,
    help="Limit table output to N columns (default: auto based on terminal width).",
)
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
    help="Path to .env file (used with --dotenv).",
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
@click.option(
    "--log-file", type=click.Path(dir_okay=False), default=None, help="Override log file path."
)
@click.option("--no-log-file", is_flag=True, help="Disable file logging explicitly.")
@click.option(
    "--session-cache",
    type=click.Path(file_okay=False),
    default=None,
    help="Enable session caching using the specified directory.",
)
@click.option("--no-cache", is_flag=True, help="Disable session caching.")
@click.version_option(version=affinity.__version__, prog_name="xaffinity")
@click.pass_context
def cli(
    click_ctx: click.Context,
    *,
    output: str,
    json_flag: bool,
    quiet: bool,
    verbose: int,
    pager: bool | None,
    all_columns: bool,
    max_columns: int | None,
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
    session_cache: str | None,
    no_cache: bool,
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

    # Set session cache environment variable if --session-cache flag is passed
    # This ensures SessionCacheConfig picks up the value via its standard environment check
    if session_cache:
        os.environ["AFFINITY_SESSION_CACHE"] = session_cache

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
        all_columns=all_columns,
        max_columns=max_columns,
        _paths=paths,
    )

    # Set no_cache flag on context
    if no_cache:
        click_ctx.obj._no_cache = True

    click_ctx.call_on_close(click_ctx.obj.close)

    previous_logging = configure_logging(
        verbosity=verbose,
        log_file=effective_log_file,
        enable_file=enable_log_file,
        api_key_for_redaction=None,
    )
    click_ctx.call_on_close(lambda: restore_logging(previous_logging))


# Register commands
from .commands.company_cmds import company_group as _company_group
from .commands.completion_cmd import completion_cmd as _completion_cmd
from .commands.config_cmds import config_group as _config_group
from .commands.entry_cmds import entry_group as _entry_group
from .commands.field_cmds import field_group as _field_group
from .commands.interaction_cmds import interaction_group as _interaction_group
from .commands.list_cmds import list_group as _list_group
from .commands.note_cmds import note_group as _note_group
from .commands.opportunity_cmds import opportunity_group as _opportunity_group
from .commands.person_cmds import person_group as _person_group
from .commands.query_cmd import query_cmd as _query_cmd
from .commands.relationship_strength_cmds import (
    relationship_strength_group as _relationship_strength_group,
)
from .commands.reminder_cmds import reminder_group as _reminder_group
from .commands.resolve_url_cmd import resolve_url_cmd as _resolve_url_cmd
from .commands.session_cmds import session_group as _session_group
from .commands.task_cmds import task_group as _task_group
from .commands.version_cmd import version_cmd as _version_cmd
from .commands.whoami_cmd import whoami_cmd as _whoami_cmd

cli.add_command(_completion_cmd)
cli.add_command(_version_cmd)
cli.add_command(_config_group)
cli.add_command(_whoami_cmd)
cli.add_command(_resolve_url_cmd)
cli.add_command(_person_group)
cli.add_command(_company_group)
cli.add_command(_opportunity_group)
cli.add_command(_list_group)
cli.add_command(_entry_group)
cli.add_command(_note_group)
cli.add_command(_reminder_group)
cli.add_command(_interaction_group)
cli.add_command(_field_group)
cli.add_command(_relationship_strength_group)
cli.add_command(_session_group)
cli.add_command(_task_group)
cli.add_command(_query_cmd)
