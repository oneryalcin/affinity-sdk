from __future__ import annotations

from typing import Any, cast

import click

rich_click: Any
try:
    import rich_click as _rich_click  # pyright: ignore[reportMissingImports]
except ModuleNotFoundError:  # pragma: no cover
    rich_click = None
else:
    rich_click = _rich_click

if rich_click is not None:  # pragma: no cover
    RichGroup = cast(type[click.Group], rich_click.RichGroup)
    RichCommand = cast(type[click.Command], rich_click.RichCommand)
else:
    RichGroup = click.Group
    RichCommand = click.Command

__all__ = ["RichCommand", "RichGroup"]
