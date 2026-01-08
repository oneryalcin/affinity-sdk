from __future__ import annotations

import io

from rich.console import Console

from affinity.cli.render import _table_from_rows


def test_table_from_rows_humanizes_typed_person_value() -> None:
    table, _ = _table_from_rows(
        [
            {
                "id": "source-of-introduction",
                "value": {
                    "type": "person",
                    "data": {
                        "id": 42,
                        "firstName": "Ada",
                        "lastName": "Lovelace",
                        "primaryEmailAddress": "ada@example.com",
                        "type": "person",
                    },
                },
            }
        ]
    )
    console = Console(file=io.StringIO(), force_terminal=True, width=220)
    rendered = "\n".join(str(line) for line in console.render_lines(table, options=console.options))
    assert "Ada Lovelace" in rendered
    assert "<ada@example.com>" in rendered
    assert "(id=42)" in rendered


def test_table_from_rows_humanizes_typed_interaction_value() -> None:
    table, _ = _table_from_rows(
        [
            {
                "id": "first-email",
                "value": {
                    "type": "interaction",
                    "data": {
                        "id": 1001,
                        "type": "email",
                        "sentAt": "2025-01-02T03:04:05Z",
                        "subject": "Hello there",
                        "from": [],
                        "to": [],
                        "cc": [],
                    },
                },
            }
        ]
    )
    console = Console(file=io.StringIO(), force_terminal=True, width=220)
    rendered = "\n".join(str(line) for line in console.render_lines(table, options=console.options))
    assert "email" in rendered
    assert "2025-01-02 03:04:05" in rendered
    assert "Hello there" in rendered
    assert "(id=1001)" in rendered


def test_table_from_rows_formats_quantity_but_not_ids() -> None:
    table, _ = _table_from_rows([{"id": 1234567, "count": 1234567}])
    console = Console(file=io.StringIO(), force_terminal=True, width=120)
    rendered = "\n".join(str(line) for line in console.render_lines(table, options=console.options))
    assert "1234567" in rendered
    assert "1,234,567" in rendered


def test_table_from_rows_formats_money_with_currency_from_name() -> None:
    table, _ = _table_from_rows(
        [
            {
                "name": "Total Funding Amount (EUR)",
                "value": {"type": "number", "data": 310000.0},
            }
        ]
    )
    console = Console(file=io.StringIO(), force_terminal=True, width=200)
    rendered = "\n".join(str(line) for line in console.render_lines(table, options=console.options))
    assert "€310,000" in rendered


def test_table_from_rows_formats_year_without_thousands_separator() -> None:
    table, _ = _table_from_rows(
        [{"name": "Year Founded", "value": {"type": "number", "data": 2019.0}}]
    )
    console = Console(file=io.StringIO(), force_terminal=True, width=120)
    rendered = "\n".join(str(line) for line in console.render_lines(table, options=console.options))
    assert "2019" in rendered
    assert "2,019" not in rendered


def test_table_from_rows_humanizes_dropdown_multi_from_dict_items() -> None:
    table, _ = _table_from_rows(
        [
            {
                "name": "Reason for Passing",
                "value": {
                    "type": "dropdown-multi",
                    "data": [{"dropdownOptionId": 1, "text": "Not a fit"}],
                },
            }
        ]
    )
    console = Console(file=io.StringIO(), force_terminal=True, width=120)
    rendered = "\n".join(str(line) for line in console.render_lines(table, options=console.options))
    assert "Not a fit" in rendered
    assert "object" not in rendered
