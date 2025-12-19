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
    fn = click.option(
        "--output",
        type=click.Choice(["table", "json"]),
        default=None,
        help="Override output format for this command.",
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
