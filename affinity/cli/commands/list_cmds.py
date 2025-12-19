from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Literal, cast

from rich.console import Console
from rich.progress import BarColumn, Progress, TaskID, TextColumn, TimeElapsedColumn

from affinity.models.entities import AffinityList, FieldMetadata, ListEntryWithEntity
from affinity.models.pagination import PaginatedResponse
from affinity.models.types import ListType
from affinity.types import ListId

from ..click_compat import RichCommand, RichGroup, click
from ..context import CLIContext
from ..csv_utils import write_csv
from ..errors import CLIError
from ..options import output_options
from ..resolve import (
    list_all_saved_views,
    list_fields_for_list,
    resolve_list_selector,
    resolve_saved_view,
)
from ..results import Artifact
from ..runner import CommandOutput, run_command


@click.group(name="list", cls=RichGroup)
def list_group() -> None:
    """List commands."""


def _parse_list_type(value: str | None) -> ListType | None:
    if value is None:
        return None
    value = value.lower()
    if value in {"person", "people"}:
        return ListType.PERSON
    if value in {"company", "companies", "organization", "org"}:
        return ListType.ORGANIZATION
    if value in {"opportunity", "opp"}:
        return ListType.OPPORTUNITY
    raise CLIError(f"Unknown list type: {value}", exit_code=2, error_type="usage_error")


@list_group.command(name="ls", cls=RichCommand)
@click.option("--type", "list_type", type=str, default=None, help="Filter by list type.")
@click.option("--page-size", type=int, default=None, help="v2 page size (limit).")
@click.option("--cursor", type=str, default=None, help="Resume from a prior cursor.")
@click.option("--max-results", type=int, default=None, help="Stop after N items total.")
@click.option("--all", "all_pages", is_flag=True, help="Fetch all pages.")
@output_options
@click.pass_obj
def list_ls(
    ctx: CLIContext,
    *,
    list_type: str | None,
    page_size: int | None,
    cursor: str | None,
    max_results: int | None,
    all_pages: bool,
) -> None:
    def fn(ctx: CLIContext, warnings: list[str]) -> CommandOutput:
        client = ctx.get_client(warnings=warnings)
        lt = _parse_list_type(list_type)

        if cursor is not None and page_size is not None:
            raise CLIError(
                "--cursor cannot be combined with --page-size.",
                exit_code=2,
                error_type="usage_error",
            )

        def fetch_page(next_cursor: str | None) -> PaginatedResponse[AffinityList]:
            page = (
                client.lists.list(cursor=next_cursor)
                if next_cursor is not None
                else client.lists.list(limit=page_size)
            )
            items = list(page.data)
            if lt is not None:
                items = [x for x in items if x.type == lt]
            return PaginatedResponse[AffinityList](data=items, pagination=page.pagination)

        page = fetch_page(cursor)
        rows: list[dict[str, object]] = []
        for item in page.data:
            rows.append(
                {
                    "id": int(item.id),
                    "name": item.name,
                    "type": item.type,
                    "ownerId": int(item.owner_id) if getattr(item, "owner_id", None) else None,
                    "isPublic": getattr(item, "is_public", None),
                }
            )
            if max_results is not None and len(rows) >= max_results:
                return CommandOutput(
                    data=rows[:max_results],
                    pagination={"nextCursor": page.pagination.next_cursor},
                    api_called=True,
                )

        if not all_pages and max_results is None:
            return CommandOutput(
                data=rows,
                pagination=(
                    {"nextCursor": page.pagination.next_cursor}
                    if page.pagination.next_cursor
                    else None
                ),
                api_called=True,
            )

        next_cursor = page.pagination.next_cursor
        while next_cursor:
            page = fetch_page(next_cursor)
            next_cursor = page.pagination.next_cursor
            for item in page.data:
                rows.append(
                    {
                        "id": int(item.id),
                        "name": item.name,
                        "type": item.type,
                        "ownerId": int(item.owner_id) if getattr(item, "owner_id", None) else None,
                        "isPublic": getattr(item, "is_public", None),
                    }
                )
                if max_results is not None and len(rows) >= max_results:
                    return CommandOutput(
                        data=rows[:max_results],
                        pagination={"nextCursor": next_cursor},
                        api_called=True,
                    )
        return CommandOutput(data=rows, pagination=None, api_called=True)

    run_command(ctx, command="list ls", fn=fn)


@list_group.command(name="view", cls=RichCommand)
@click.argument("list_selector")
@output_options
@click.pass_obj
def list_view(ctx: CLIContext, list_selector: str) -> None:
    def fn(ctx: CLIContext, warnings: list[str]) -> CommandOutput:
        client = ctx.get_client(warnings=warnings)
        resolved = resolve_list_selector(client=client, selector=list_selector)
        list_id = ListId(int(resolved.list.id))
        fields = client.lists.get_fields(list_id)
        views = list_all_saved_views(client=client, list_id=list_id)
        data = {
            "list": resolved.list.model_dump(by_alias=True, mode="json"),
            "fields": [f.model_dump(by_alias=True, mode="json") for f in fields],
            "savedViews": [v.model_dump(by_alias=True, mode="json") for v in views],
        }
        return CommandOutput(data=data, resolved=resolved.resolved, api_called=True)

    run_command(ctx, command="list view", fn=fn)


CsvHeaderMode = Literal["names", "ids"]


@list_group.command(name="export", cls=RichCommand)
@click.argument("list_selector")
@click.option("--saved-view", type=str, default=None, help="Saved view id or name.")
@click.option("--field", "fields", type=str, multiple=True, help="Field name or id (repeatable).")
@click.option(
    "--filter",
    "filter_expr",
    type=str,
    default=None,
    help="V2 filter string (mutually exclusive with --saved-view).",
)
@click.option("--page-size", type=int, default=200, show_default=True, help="v2 page size (limit).")
@click.option("--cursor", type=str, default=None, help="Resume from a prior cursor.")
@click.option("--max-results", type=int, default=None, help="Stop after N rows total.")
@click.option("--all", "all_pages", is_flag=True, help="Fetch all rows.")
@click.option("--csv", "csv_path", type=click.Path(), default=None, help="Write CSV.")
@click.option(
    "--csv-header",
    type=click.Choice(["names", "ids"]),
    default="names",
    show_default=True,
)
@click.option("--csv-bom", is_flag=True, help="Write UTF-8 BOM for Excel.")
@click.option("--dry-run", is_flag=True, help="Validate selectors and print export plan.")
@output_options
@click.pass_obj
def list_export(
    ctx: CLIContext,
    list_selector: str,
    *,
    saved_view: str | None,
    fields: tuple[str, ...],
    filter_expr: str | None,
    page_size: int,
    cursor: str | None,
    max_results: int | None,
    all_pages: bool,
    csv_path: str | None,
    csv_header: CsvHeaderMode,
    csv_bom: bool,
    dry_run: bool,
) -> None:
    def fn(ctx: CLIContext, warnings: list[str]) -> CommandOutput:
        if saved_view and filter_expr:
            raise CLIError(
                "--saved-view and --filter are mutually exclusive.",
                exit_code=2,
                error_type="usage_error",
            )
        if cursor and (saved_view or filter_expr or fields):
            raise CLIError(
                "--cursor cannot be combined with --saved-view/--filter/--field.",
                exit_code=2,
                error_type="usage_error",
            )
        if cursor and page_size != 200:
            raise CLIError(
                "--cursor cannot be combined with --page-size (cursor encodes page size).",
                exit_code=2,
                error_type="usage_error",
            )

        client = ctx.get_client(warnings=warnings)
        resolved_list = resolve_list_selector(client=client, selector=list_selector)
        list_id = ListId(int(resolved_list.list.id))
        resolved: dict[str, Any] = dict(resolved_list.resolved)

        # Resolve columns/fields.
        field_meta = list_fields_for_list(client=client, list_id=list_id)
        field_by_id: dict[str, FieldMetadata] = {str(f.id): f for f in field_meta}

        selected_field_ids: list[str] = []
        if saved_view:
            view, view_resolved = resolve_saved_view(
                client=client, list_id=list_id, selector=saved_view
            )
            resolved.update(view_resolved)
            selected_field_ids = list(view.field_ids)
            if fields:
                requested_ids = _resolve_field_selectors(fields=fields, field_by_id=field_by_id)
                missing = [fid for fid in requested_ids if fid not in selected_field_ids]
                if missing:
                    message = (
                        "When using --saved-view, --field may only subset/reorder the "
                        "saved view columns."
                    )
                    raise CLIError(
                        message,
                        exit_code=2,
                        error_type="usage_error",
                        details={
                            "missingFieldIds": missing,
                            "savedViewFieldIds": selected_field_ids,
                        },
                    )
                selected_field_ids = requested_ids
        elif fields:
            selected_field_ids = _resolve_field_selectors(fields=fields, field_by_id=field_by_id)
        else:
            selected_field_ids = [str(f.id) for f in field_meta]

        columns = _columns_meta(selected_field_ids, field_by_id=field_by_id)

        if dry_run:
            data = {
                "listId": int(list_id),
                "savedView": saved_view,
                "fieldIds": selected_field_ids,
                "filter": filter_expr,
                "pageSize": page_size,
                "cursor": cursor,
                "csv": str(csv_path) if csv_path else None,
            }
            return CommandOutput(
                data=data,
                resolved=resolved,
                columns=columns,
                api_called=True,
            )

        # Prepare CSV writing.
        csv_path_obj = Path(csv_path) if csv_path is not None else None
        want_csv = csv_path_obj is not None
        rows_written = 0
        next_url: str | None = None

        progress: Progress | None = None
        task_id: TaskID | None = None
        if (
            ctx.progress != "never"
            and not ctx.quiet
            and (ctx.progress == "always" or sys.stderr.isatty())
        ):
            progress = Progress(
                TextColumn("{task.description}"),
                BarColumn(),
                TextColumn("{task.completed} rows"),
                TimeElapsedColumn(),
                console=Console(file=sys.stderr),
                transient=True,
            )
            progress.__enter__()
            task_id = progress.add_task("export", total=max_results if max_results else None)

        if want_csv:
            assert csv_path_obj is not None
            field_headers = [
                (
                    (field_by_id[fid].name if fid in field_by_id else fid)
                    if csv_header == "names"
                    else fid
                )
                for fid in selected_field_ids
            ]
            header = ["listEntryId", "entityType", "entityId", "entityName", *field_headers]
            temp_path = csv_path_obj.with_suffix(csv_path_obj.suffix + ".tmp")

            def iter_rows() -> Any:
                nonlocal rows_written, next_url
                for row, page_next_url in _iterate_list_entries(
                    client=client,
                    list_id=list_id,
                    saved_view=saved_view,
                    filter_expr=filter_expr,
                    selected_field_ids=selected_field_ids,
                    page_size=page_size,
                    cursor=cursor,
                    max_results=max_results,
                    all_pages=all_pages,
                    field_by_id=field_by_id,
                    key_mode=csv_header,
                ):
                    next_url = page_next_url
                    rows_written += 1
                    if progress is not None and task_id is not None:
                        progress.update(task_id, completed=rows_written)
                    yield row

            write_result = write_csv(
                path=temp_path,
                rows=iter_rows(),
                fieldnames=header,
                bom=csv_bom,
            )
            temp_path.replace(csv_path_obj)

            csv_ref, csv_is_relative = _artifact_path(csv_path_obj)
            data = {
                "listId": int(list_id),
                "rowsWritten": rows_written,
                "csv": csv_ref,
            }
            if progress is not None:
                progress.__exit__(None, None, None)
            return CommandOutput(
                data=data,
                artifacts=[
                    Artifact(
                        type="csv",
                        path=csv_ref,
                        path_is_relative=csv_is_relative,
                        rows_written=write_result.rows_written,
                        bytes_written=write_result.bytes_written,
                        partial=False,
                    )
                ],
                pagination={"nextCursor": next_url} if next_url else None,
                resolved=resolved,
                columns=columns,
                api_called=True,
            )

        # JSON/table rows in-memory (small exports).
        rows: list[dict[str, Any]] = []
        for row, page_next_url in _iterate_list_entries(
            client=client,
            list_id=list_id,
            saved_view=saved_view,
            filter_expr=filter_expr,
            selected_field_ids=selected_field_ids,
            page_size=page_size,
            cursor=cursor,
            max_results=max_results,
            all_pages=all_pages,
            field_by_id=field_by_id,
            key_mode="names",
        ):
            next_url = page_next_url
            rows.append(row)
            if progress is not None and task_id is not None:
                progress.update(task_id, completed=len(rows))

        if progress is not None:
            progress.__exit__(None, None, None)

        return CommandOutput(
            data=rows,
            pagination={"nextCursor": next_url} if next_url else None,
            resolved=resolved,
            columns=columns,
            api_called=True,
        )

    run_command(ctx, command="list export", fn=fn)


def _artifact_path(path: Path) -> tuple[str, bool]:
    try:
        rel = path.resolve().relative_to(Path.cwd().resolve())
        return str(rel), True
    except Exception:
        return str(path.resolve()), False


def _resolve_field_selectors(
    *,
    fields: tuple[str, ...],
    field_by_id: dict[str, FieldMetadata],
) -> list[str]:
    resolved: list[str] = []
    # Build name index for list-scoped fields
    by_name: dict[str, list[str]] = {}
    for fid, meta in field_by_id.items():
        by_name.setdefault(meta.name.lower(), []).append(fid)

    for raw in fields:
        raw = raw.strip()
        if not raw:
            continue
        if raw.isdigit():
            resolved.append(raw)
            continue
        # treat as ID if exact key exists
        if raw in field_by_id:
            resolved.append(raw)
            continue
        matches = by_name.get(raw.lower(), [])
        if not matches:
            raise CLIError(f'Unknown field: "{raw}"', exit_code=2, error_type="usage_error")
        if len(matches) > 1:
            raise CLIError(
                f'Ambiguous field name: "{raw}"',
                exit_code=2,
                error_type="ambiguous_resolution",
                details={"name": raw, "fieldIds": matches},
            )
        resolved.append(matches[0])
    return resolved


def _columns_meta(
    field_ids: list[str],
    *,
    field_by_id: dict[str, FieldMetadata],
) -> list[dict[str, Any]]:
    cols: list[dict[str, Any]] = []
    for fid in field_ids:
        meta = field_by_id.get(fid)
        cols.append(
            {
                "fieldId": fid,
                "fieldName": meta.name if meta else fid,
                "fieldType": meta.type if meta else None,
                "valueType": meta.value_type if meta else None,
            }
        )
    return cols


def _iterate_list_entries(
    *,
    client: Any,
    list_id: ListId,
    saved_view: str | None,
    filter_expr: str | None,
    selected_field_ids: list[str],
    page_size: int,
    cursor: str | None,
    max_results: int | None,
    all_pages: bool,
    field_by_id: dict[str, FieldMetadata],
    key_mode: Literal["names", "ids"],
) -> Any:
    """
    Yield `(row_dict, next_cursor)` where `next_cursor` is the resume token after the yielded row.
    """
    fetched = 0

    entries = client.lists.entries(list_id)

    next_cursor: str | None = None
    if cursor:
        page = entries.list(cursor=cursor)
    elif saved_view:
        view, _ = resolve_saved_view(client=client, list_id=list_id, selector=saved_view)
        page = entries.from_saved_view(view.id, limit=page_size)
    else:
        page = entries.list(
            field_ids=selected_field_ids,
            filter=filter_expr,
            limit=page_size,
        )

    next_cursor = page.pagination.next_cursor
    for entry in page.data:
        fetched += 1
        yield _entry_to_row(entry, selected_field_ids, field_by_id, key_mode=key_mode), next_cursor
        if max_results is not None and fetched >= max_results:
            return

    if not all_pages and max_results is None:
        return

    while next_cursor:
        page = entries.list(cursor=next_cursor)
        next_cursor = page.pagination.next_cursor
        for entry in page.data:
            fetched += 1
            yield (
                _entry_to_row(entry, selected_field_ids, field_by_id, key_mode=key_mode),
                next_cursor,
            )
            if max_results is not None and fetched >= max_results:
                return


def _entry_to_row(
    entry: ListEntryWithEntity,
    field_ids: list[str],
    field_by_id: dict[str, FieldMetadata],
    *,
    key_mode: Literal["names", "ids"],
) -> dict[str, Any]:
    entity_id: int | None = None
    entity_name: str | None = None
    if entry.entity is not None:
        entity_id = int(entry.entity.id)
        entity_name = getattr(entry.entity, "name", None)
        if entity_name is None and hasattr(entry.entity, "full_name"):
            entity_name = cast(Any, entry.entity).full_name
    row: dict[str, Any] = {
        "listEntryId": int(entry.id),
        "entityType": entry.type,
        "entityId": entity_id,
        "entityName": entity_name,
    }
    for fid in field_ids:
        key = fid if key_mode == "ids" else field_by_id[fid].name if fid in field_by_id else fid
        row[key] = entry.fields.data.get(str(fid))
    return row
