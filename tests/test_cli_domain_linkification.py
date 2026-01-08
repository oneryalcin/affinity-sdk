from __future__ import annotations

import io

from rich.console import Console

from affinity.cli.render import _table_from_rows


def test_table_from_rows_urlifies_domain_columns() -> None:
    table, _ = _table_from_rows(
        [
            {
                "id": 1,
                "domain": "example.com",
                "domains": ["example.com", "www.example.com"],
            }
        ]
    )

    console = Console(file=io.StringIO(), force_terminal=True, width=200)
    rendered = "\n".join(str(line) for line in console.render_lines(table, options=console.options))
    assert "https://example.com" in rendered
    assert "https://www.example.com" in rendered
