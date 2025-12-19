from __future__ import annotations

import io
import sys

from rich.console import Console, Group
from rich.table import Table

from affinity.cli.render import RenderSettings, _should_use_pager


def _stdout_console(*, height: int) -> Console:
    return Console(file=io.StringIO(), force_terminal=True, width=80, height=height)


def test_should_use_pager_auto_does_not_page_small_table(monkeypatch: object) -> None:
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    stdout = _stdout_console(height=20)

    table = Table()
    table.add_column("id")
    table.add_row("1")

    settings = RenderSettings(output="table", quiet=False, verbosity=0, pager=None)
    assert _should_use_pager(settings=settings, stdout=stdout, renderable=table) is False


def test_should_use_pager_auto_pages_large_table(monkeypatch: object) -> None:
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    stdout = _stdout_console(height=5)

    table = Table()
    table.add_column("id")
    for i in range(50):
        table.add_row(str(i))

    settings = RenderSettings(output="table", quiet=False, verbosity=0, pager=None)
    assert _should_use_pager(settings=settings, stdout=stdout, renderable=table) is True


def test_should_use_pager_auto_pages_large_group(monkeypatch: object) -> None:
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    stdout = _stdout_console(height=5)

    t1 = Table()
    t1.add_column("x")
    t1.add_row("a")

    t2 = Table()
    t2.add_column("y")
    for i in range(50):
        t2.add_row(str(i))

    settings = RenderSettings(output="table", quiet=False, verbosity=0, pager=None)
    assert _should_use_pager(settings=settings, stdout=stdout, renderable=Group(t1, t2)) is True
