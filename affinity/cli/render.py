from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from typing import Any, cast

from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from affinity.models.rate_limit_snapshot import RateLimitSnapshot

from .results import CommandResult


@dataclass(frozen=True, slots=True)
class RenderSettings:
    output: str  # "table" | "json"
    quiet: bool
    verbosity: int
    pager: bool | None  # None=auto


def _error_title(error_type: str) -> str:
    normalized = (error_type or "").strip()
    mapping = {
        "usage_error": "Usage error",
        "ambiguous_resolution": "Ambiguous",
        "not_found": "Not found",
        "AuthenticationError": "Authentication error",
        "AuthorizationError": "Permission denied",
        "NotFoundError": "Not found",
        "RateLimitError": "Rate limited",
        "ServerError": "Server error",
    }
    return mapping.get(normalized, "Error")


def _render_error_details(
    *,
    stderr: Console,
    command: str,
    error_type: str,
    message: str,
    details: dict[str, Any] | None,
    settings: RenderSettings,
) -> None:
    if settings.quiet:
        return
    if not details:
        if error_type == "ambiguous_resolution":
            stderr.print(f"Hint: run `affinity {command} --help`")
        elif error_type == "usage_error":
            # Avoid noisy hints for credential/config errors where --help doesn't help.
            lowered = message.lower()
            if "api key" not in lowered and "python-dotenv" not in lowered:
                stderr.print(f"Hint: run `affinity {command} --help`")
        return

    if error_type == "ambiguous_resolution":
        matches = details.get("matches")
        if isinstance(matches, list) and matches and all(isinstance(m, dict) for m in matches):
            matches = cast(list[dict[str, Any]], matches)
            preferred = ["listId", "savedViewId", "fieldId", "id", "name", "type", "isDefault"]
            columns: list[str] = []
            for key in preferred:
                if any(key in m for m in matches):
                    columns.append(key)
            if not columns:
                columns = list(matches[0].keys())[:4]

            table = Table(show_header=True, header_style="bold")
            for col in columns:
                table.add_column(col)
            for m in matches[:20]:
                table.add_row(*[str(m.get(col, "")) for col in columns])
            stderr.print(table)
        elif "fieldIds" in details and isinstance(details.get("fieldIds"), list):
            field_ids = details.get("fieldIds")
            stderr.print("Matches: " + ", ".join(str(x) for x in cast(list[Any], field_ids)[:20]))

        stderr.print(f"Hint: run `affinity {command} --help`")
        return

    if error_type == "usage_error":
        stderr.print(f"Hint: run `affinity {command} --help`")
        if settings.verbosity >= 1:
            stderr.print(Panel.fit(Text(json.dumps(details, ensure_ascii=False, indent=2))))
        return

    if settings.verbosity >= 2:
        stderr.print(Panel.fit(Text(json.dumps(details, ensure_ascii=False, indent=2))))


def _rate_limit_footer(snapshot: RateLimitSnapshot) -> str:
    def _fmt_int(value: int | None) -> str | None:
        if value is None:
            return None
        return f"{value:,}"

    def _fmt_reset_seconds(seconds: int | None) -> str | None:
        if seconds is None:
            return None
        total_seconds = max(0, int(seconds))
        days = total_seconds // 86400
        if days:
            return f"{days:,}d"
        hours = (total_seconds % 86400) // 3600
        minutes = (total_seconds % 3600) // 60
        secs = total_seconds % 60
        return f"{hours}:{minutes:02}:{secs:02}"

    parts: list[str] = []
    user = snapshot.api_key_per_minute
    if user.limit is not None or user.remaining is not None:
        user_bits: list[str] = []
        user_remaining = _fmt_int(user.remaining)
        user_limit = _fmt_int(user.limit)
        if user_remaining is not None and user_limit is not None:
            user_bits.append(f"user {user_remaining}/{user_limit}")
        elif user_remaining is not None:
            user_bits.append(f"user remaining {user_remaining}")
        user_reset = _fmt_reset_seconds(user.reset_seconds)
        if user_reset is not None:
            user_bits.append(f"reset {user_reset}")
        parts.append(" ".join(user_bits))

    org = snapshot.org_monthly
    if org.limit is not None or org.remaining is not None:
        org_bits: list[str] = []
        org_remaining = _fmt_int(org.remaining)
        org_limit = _fmt_int(org.limit)
        if org_remaining is not None and org_limit is not None:
            org_bits.append(f"org {org_remaining}/{org_limit}")
        elif org_remaining is not None:
            org_bits.append(f"org remaining {org_remaining}")
        org_reset = _fmt_reset_seconds(org.reset_seconds)
        if org_reset is not None:
            org_bits.append(f"reset {org_reset}")
        parts.append(" ".join(org_bits))

    if not parts:
        return ""
    return "Rate limit: " + " | ".join(parts)


def _table_from_rows(rows: list[dict[str, Any]]) -> Table:
    table = Table(show_header=True, header_style="bold")
    if not rows:
        table.add_column("result")
        table.add_row("No results")
        return table
    columns = list(rows[0].keys())
    for col in columns:
        table.add_column(col)
    for row in rows:
        table.add_row(*[str(row.get(c, "")) for c in columns])
    return table


def _should_use_pager(*, settings: RenderSettings, stdout: Console, renderable: Any) -> bool:
    if settings.pager is False:
        return False
    if settings.pager is True:
        return True

    # Auto mode: only page when interactive and the output is likely to scroll
    # (tables, or output taller than the terminal).
    if not sys.stdout.isatty():
        return False
    if isinstance(renderable, Table):
        return True
    if isinstance(renderable, Group) and any(isinstance(r, Table) for r in renderable.renderables):
        return True

    try:
        height = stdout.size.height
        if not height:
            return False
        lines = stdout.render_lines(renderable, options=stdout.options, pad=False)
        return len(lines) > height
    except Exception:
        return False


def render_result(result: CommandResult, *, settings: RenderSettings) -> int:
    stdout = Console(file=sys.stdout, force_terminal=False)
    stderr = Console(file=sys.stderr, force_terminal=False)

    if settings.output == "json":
        payload = result.model_dump(by_alias=True, mode="json")
        sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
        return 0

    # table/human output
    if not result.ok:
        if result.error is not None:
            title = _error_title(result.error.type)
            stderr.print(f"{title}: {result.error.message}")
            _render_error_details(
                stderr=stderr,
                command=result.command,
                error_type=result.error.type,
                message=result.error.message,
                details=result.error.details,
                settings=settings,
            )
        else:
            stderr.print("Error")
        return 0

    renderable: Any
    if result.command == "version" and isinstance(result.data, dict):
        renderable = Text(result.data.get("version", ""), style="bold")
    elif result.command == "config path" and isinstance(result.data, dict):
        renderable = Text(str(result.data.get("path", "")))
    elif result.command == "config init" and isinstance(result.data, dict):
        renderable = Panel.fit(Text(f"Initialized config at {result.data.get('path', '')}"))
    elif result.command == "resolve-url" and isinstance(result.data, dict):
        renderable = Text(
            f"{result.data.get('type')} {result.data.get('canonicalUrl', '')}".strip()
        )
    elif result.command == "whoami" and isinstance(result.data, dict):
        tenant = (
            result.data.get("tenant", {}) if isinstance(result.data.get("tenant"), dict) else {}
        )
        user = result.data.get("user", {}) if isinstance(result.data.get("user"), dict) else {}
        title = tenant.get("name") or "Affinity"
        body = (
            f"{user.get('firstName', '')} {user.get('lastName', '') or ''}\n"
            f"{user.get('emailAddress', '')}"
        )
        renderable = Panel.fit(Text(body.strip()), title=str(title))
    elif result.command == "list view" and isinstance(result.data, dict):
        list_obj = result.data.get("list", {})
        header = Text(f"List {list_obj.get('name', '')} ({list_obj.get('id', '')})", style="bold")
        fields = (
            result.data.get("fields", []) if isinstance(result.data.get("fields"), list) else []
        )
        views = (
            result.data.get("savedViews", [])
            if isinstance(result.data.get("savedViews"), list)
            else []
        )
        show_is_default = any(isinstance(v, dict) and v.get("isDefault") is not None for v in views)
        fields_table = _table_from_rows(
            [
                {"id": f.get("id"), "name": f.get("name"), "valueType": f.get("valueType")}
                for f in fields
                if isinstance(f, dict)
            ]
        )
        views_table = _table_from_rows(
            [
                {"id": v.get("id"), "name": v.get("name"), "isDefault": v.get("isDefault")}
                if show_is_default
                else {"id": v.get("id"), "name": v.get("name")}
                for v in views
                if isinstance(v, dict)
            ]
        )
        renderable = Group(
            Panel.fit(
                Text.assemble(header, "\n\n", Text("Fields", style="bold"), "\n"),
                subtitle="(see tables below)",
            ),
            fields_table,
            Text("\nSaved Views", style="bold"),
            views_table,
        )
    else:
        data = result.data
        if isinstance(data, list) and all(isinstance(x, dict) for x in data):
            renderable = _table_from_rows(cast(list[dict[str, Any]], data))
        elif isinstance(data, dict):
            renderable = Panel.fit(Text(json.dumps(data, ensure_ascii=False, indent=2)))
        else:
            renderable = Panel.fit(Text(str(data) if data is not None else "OK"))

    if renderable is not None:
        if _should_use_pager(settings=settings, stdout=stdout, renderable=renderable):
            with stdout.pager():
                stdout.print(renderable)
        else:
            stdout.print(renderable)

    if result.meta.rate_limit is not None:
        footer = _rate_limit_footer(result.meta.rate_limit)
        if footer:
            stdout.print(footer)

    return 0
