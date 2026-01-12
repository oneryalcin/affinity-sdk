from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from .click_compat import click
from .context import CLIContext

F = TypeVar("F", bound=Callable[..., object])


def _set_output(ctx: click.Context, _param: click.Parameter, value: str | None) -> str | None:
    if value is None:
        return value
    obj = ctx.obj
    if isinstance(obj, CLIContext):
        obj.output = value  # type: ignore[assignment]
    return value


def _set_json(ctx: click.Context, _param: click.Parameter, value: bool) -> bool:
    if not value:
        return value
    obj = ctx.obj
    if isinstance(obj, CLIContext):
        obj.output = "json"
    return value


def output_options(fn: F) -> F:
    """Add output format options to a command.

    Adds --output/-o and --json flags. Note: --csv is NOT included here
    because individual commands have their own --csv flags with additional
    options (--csv-bom, --csv-header, --csv-mode).
    """
    fn = click.option(
        "--output",
        "-o",
        type=click.Choice(["table", "json", "jsonl", "markdown", "toon", "csv"]),
        default=None,
        help="Output format (default: table for terminal, json for pipes).",
        callback=_set_output,
        expose_value=False,
    )(fn)
    fn = click.option(
        "--json",
        is_flag=True,
        help="Alias for --output json.",
        callback=_set_json,
        expose_value=False,
    )(fn)
    return fn
