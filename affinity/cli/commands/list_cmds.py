from __future__ import annotations

import sys
from contextlib import ExitStack
from pathlib import Path
from typing import Any, Literal, cast

from rich.console import Console
from rich.progress import BarColumn, Progress, TaskID, TextColumn, TimeElapsedColumn

from affinity.models.entities import FieldMetadata, ListCreate, ListEntryWithEntity
from affinity.models.types import ListType
from affinity.types import (
    AnyFieldId,
    CompanyId,
    EnrichedFieldId,
    FieldId,
    ListEntryId,
    ListId,
    OpportunityId,
    PersonId,
)

from ..click_compat import RichCommand, RichGroup, click
from ..context import CLIContext
from ..csv_utils import artifact_path, write_csv
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
from ..serialization import serialize_model_for_cli, serialize_models_for_cli
from ._v1_parsing import parse_json_value


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
@click.option("--page-size", type=int, default=None, help="Page size (limit).")
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
    """
    List all lists in the workspace.

    Examples:

    - `xaffinitylist ls`
    - `xaffinitylist ls --type person`
    - `xaffinitylist ls --type company --all`
    """

    def fn(ctx: CLIContext, warnings: list[str]) -> CommandOutput:
        client = ctx.get_client(warnings=warnings)
        lt = _parse_list_type(list_type)

        if cursor is not None and page_size is not None:
            raise CLIError(
                "--cursor cannot be combined with --page-size.",
                exit_code=2,
                error_type="usage_error",
            )

        pages = client.lists.pages(limit=page_size, cursor=cursor)
        rows: list[dict[str, object]] = []
        first_page = True
        for page in pages:
            for idx, item in enumerate(page.data):
                if lt is not None and item.type != lt:
                    continue
                rows.append(
                    {
                        "id": int(item.id),
                        "name": item.name,
                        "type": ListType(item.type).name.lower(),
                        "ownerId": int(item.owner_id) if getattr(item, "owner_id", None) else None,
                        "isPublic": getattr(item, "is_public", None),
                    }
                )
                if max_results is not None and len(rows) >= max_results:
                    stopped_mid_page = idx < (len(page.data) - 1)
                    if stopped_mid_page:
                        warnings.append(
                            "Results truncated mid-page; resume cursor omitted "
                            "to avoid skipping items. Re-run with a higher "
                            "--max-results or without it to paginate safely."
                        )
                    pagination = None
                    if (
                        page.pagination.next_cursor
                        and not stopped_mid_page
                        and page.pagination.next_cursor != cursor
                    ):
                        pagination = {
                            "lists": {
                                "nextCursor": page.pagination.next_cursor,
                                "prevCursor": page.pagination.prev_cursor,
                            }
                        }
                    return CommandOutput(
                        data={"lists": rows[:max_results]},
                        pagination=pagination,
                        api_called=True,
                    )

            if first_page and not all_pages and max_results is None:
                return CommandOutput(
                    data={"lists": rows},
                    pagination=(
                        {
                            "lists": {
                                "nextCursor": page.pagination.next_cursor,
                                "prevCursor": page.pagination.prev_cursor,
                            }
                        }
                        if page.pagination.next_cursor
                        else None
                    ),
                    api_called=True,
                )
            first_page = False

        return CommandOutput(data={"lists": rows}, pagination=None, api_called=True)

    run_command(ctx, command="list ls", fn=fn)


@list_group.command(name="create", cls=RichCommand)
@click.option("--name", required=True, help="List name.")
@click.option("--type", "list_type", required=True, help="List type (person/company/opportunity).")
@click.option(
    "--public/--private",
    "is_public",
    default=False,
    help="Whether the list is public (default: private).",
)
@click.option("--owner-id", type=int, default=None, help="Owner id.")
@output_options
@click.pass_obj
def list_create(
    ctx: CLIContext,
    *,
    name: str,
    list_type: str,
    is_public: bool,
    owner_id: int | None,
) -> None:
    """
    Create a new list.

    Examples:

    - `xaffinitylist create --name "Prospects" --type company`
    - `xaffinitylist create --name "Candidates" --type person --public`
    """

    def fn(ctx: CLIContext, warnings: list[str]) -> CommandOutput:
        _ = warnings
        lt = _parse_list_type(list_type)
        if lt is None:
            raise CLIError(
                "Missing list type.",
                exit_code=2,
                error_type="usage_error",
                hint="Use --type person|company|opportunity.",
            )
        client = ctx.get_client(warnings=warnings)
        created = client.lists.create(
            ListCreate(
                name=name,
                type=lt,
                is_public=is_public,
                owner_id=owner_id,
            )
        )
        payload = serialize_model_for_cli(created)
        return CommandOutput(data={"list": payload}, api_called=True)

    run_command(ctx, command="list create", fn=fn)


@list_group.command(name="view", cls=RichCommand)
@click.argument("list_selector")
@output_options
@click.pass_obj
def list_view(ctx: CLIContext, list_selector: str) -> None:
    """
    View list details, fields, and saved views.

    LIST_SELECTOR can be a list id or exact list name.

    Examples:

    - `xaffinitylist view 12345`
    - `xaffinitylist view "Pipeline"`
    """

    def fn(ctx: CLIContext, warnings: list[str]) -> CommandOutput:
        client = ctx.get_client(warnings=warnings)
        resolved = resolve_list_selector(client=client, selector=list_selector)
        list_id = ListId(int(resolved.list.id))
        fields = client.lists.get_fields(list_id)
        views = list_all_saved_views(client=client, list_id=list_id)
        data = {
            "list": serialize_model_for_cli(resolved.list),
            "fields": serialize_models_for_cli(fields),
            "savedViews": serialize_models_for_cli(views),
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
    help="Filter expression (mutually exclusive with --saved-view).",
)
@click.option("--page-size", type=int, default=200, show_default=True, help="Page size (limit).")
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
    """
    Export list entries to JSON or CSV.

    LIST_SELECTOR can be a list id or exact list name.

    Examples:

    - `xaffinitylist export "Pipeline" --all`
    - `xaffinitylist export 12345 --csv pipeline.csv --all`
    - `xaffinitylist export "Pipeline" --saved-view "Active Deals" --csv deals.csv`
    - `xaffinitylist export "Pipeline" --field Status --field "Deal Size" --all`
    """

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
        next_cursor: str | None = None

        with ExitStack() as stack:
            progress: Progress | None = None
            task_id: TaskID | None = None
            if (
                ctx.progress != "never"
                and not ctx.quiet
                and (ctx.progress == "always" or sys.stderr.isatty())
            ):
                progress = stack.enter_context(
                    Progress(
                        TextColumn("{task.description}"),
                        BarColumn(),
                        TextColumn("{task.completed} rows"),
                        TimeElapsedColumn(),
                        console=Console(file=sys.stderr),
                        transient=True,
                    )
                )
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
                csv_iter_state: dict[str, Any] = {}

                def iter_rows() -> Any:
                    nonlocal rows_written, next_cursor
                    for row, page_next_cursor in _iterate_list_entries(
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
                        state=csv_iter_state,
                    ):
                        next_cursor = page_next_cursor
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

                csv_ref, csv_is_relative = artifact_path(csv_path_obj)
                data = {
                    "listId": int(list_id),
                    "rowsWritten": rows_written,
                    "csv": csv_ref,
                }
                if csv_iter_state.get("truncatedMidPage") is True:
                    warnings.append(
                        "Results truncated mid-page; resume cursor omitted "
                        "to avoid skipping items. Re-run with a higher "
                        "--max-results or without it to paginate safely."
                    )
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
                    pagination={"rows": {"nextCursor": next_cursor, "prevCursor": None}}
                    if next_cursor
                    else None,
                    resolved=resolved,
                    columns=columns,
                    api_called=True,
                )

            # JSON/table rows in-memory (small exports).
            rows: list[dict[str, Any]] = []
            table_iter_state: dict[str, Any] = {}
            for row, page_next_cursor in _iterate_list_entries(
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
                state=table_iter_state,
            ):
                next_cursor = page_next_cursor
                rows.append(row)
                if progress is not None and task_id is not None:
                    progress.update(task_id, completed=len(rows))

            if table_iter_state.get("truncatedMidPage") is True:
                warnings.append(
                    "Results truncated mid-page; resume cursor omitted "
                    "to avoid skipping items. Re-run with a higher "
                    "--max-results or without it to paginate safely."
                )
            return CommandOutput(
                data={"rows": rows},
                pagination={"rows": {"nextCursor": next_cursor, "prevCursor": None}}
                if next_cursor
                else None,
                resolved=resolved,
                columns=columns,
                api_called=True,
            )
        raise AssertionError("unreachable")

    run_command(ctx, command="list export", fn=fn)


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
    state: dict[str, Any] | None = None,
) -> Any:
    """
    Yield `(row_dict, next_cursor)` where `next_cursor` resumes at the next page (not per-row).
    """
    fetched = 0

    entries = client.lists.entries(list_id)

    if saved_view:
        next_page_cursor: str | None = None
        if cursor:
            page = entries.list(cursor=cursor)
        else:
            view, _ = resolve_saved_view(client=client, list_id=list_id, selector=saved_view)
            page = entries.from_saved_view(view.id, limit=page_size)

        next_page_cursor = page.pagination.next_cursor
        for idx, entry in enumerate(page.data):
            fetched += 1
            yield (
                _entry_to_row(entry, selected_field_ids, field_by_id, key_mode=key_mode),
                None
                if max_results is not None and fetched >= max_results and idx < (len(page.data) - 1)
                else next_page_cursor,
            )
            if max_results is not None and fetched >= max_results:
                if idx < (len(page.data) - 1) and state is not None:
                    state["truncatedMidPage"] = True
                return

        if not all_pages and max_results is None:
            return

        while next_page_cursor:
            page = entries.list(cursor=next_page_cursor)
            next_page_cursor = page.pagination.next_cursor
            for idx, entry in enumerate(page.data):
                fetched += 1
                yield (
                    _entry_to_row(entry, selected_field_ids, field_by_id, key_mode=key_mode),
                    None
                    if max_results is not None
                    and fetched >= max_results
                    and idx < (len(page.data) - 1)
                    else next_page_cursor,
                )
                if max_results is not None and fetched >= max_results:
                    if idx < (len(page.data) - 1) and state is not None:
                        state["truncatedMidPage"] = True
                    return
        return

    pages = (
        entries.pages(cursor=cursor)
        if cursor is not None
        else entries.pages(
            field_ids=selected_field_ids,
            filter=filter_expr,
            limit=page_size,
        )
    )

    first_page = True
    for page in pages:
        next_page_cursor = page.pagination.next_cursor
        for idx, entry in enumerate(page.data):
            fetched += 1
            yield (
                _entry_to_row(entry, selected_field_ids, field_by_id, key_mode=key_mode),
                None
                if max_results is not None and fetched >= max_results and idx < (len(page.data) - 1)
                else next_page_cursor,
            )
            if max_results is not None and fetched >= max_results:
                if idx < (len(page.data) - 1) and state is not None:
                    state["truncatedMidPage"] = True
                return

        if first_page and not all_pages and max_results is None:
            return
        first_page = False


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


@list_group.group(name="entry", cls=RichGroup)
def list_entry_group() -> None:
    """List entry commands."""


def _validate_entry_target(
    person_id: int | None,
    company_id: int | None,
    opportunity_id: int | None,
) -> None:
    count = sum(1 for value in (person_id, company_id, opportunity_id) if value is not None)
    if count == 1:
        return
    raise CLIError(
        "Provide exactly one of --person-id, --company-id, or --opportunity-id.",
        error_type="usage_error",
        exit_code=2,
    )


@list_entry_group.command(name="add", cls=RichCommand)
@click.argument("list_selector")
@click.option("--person-id", type=int, default=None, help="Person id to add.")
@click.option("--company-id", type=int, default=None, help="Company id to add.")
@click.option("--opportunity-id", type=int, default=None, help="Opportunity id to add.")
@click.option("--creator-id", type=int, default=None, help="Creator id override.")
@output_options
@click.pass_obj
def list_entry_add(
    ctx: CLIContext,
    list_selector: str,
    *,
    person_id: int | None,
    company_id: int | None,
    opportunity_id: int | None,
    creator_id: int | None,
) -> None:
    """Add a list entry (V1 write path)."""

    def fn(ctx: CLIContext, warnings: list[str]) -> CommandOutput:
        _validate_entry_target(person_id, company_id, opportunity_id)
        client = ctx.get_client(warnings=warnings)
        resolved_list = resolve_list_selector(client=client, selector=list_selector)
        entries = client.lists.entries(resolved_list.list.id)

        created = None
        if person_id is not None:
            created = entries.add_person(PersonId(person_id), creator_id=creator_id)
        elif company_id is not None:
            created = entries.add_company(CompanyId(company_id), creator_id=creator_id)
        else:
            assert opportunity_id is not None
            created = entries.add_opportunity(OpportunityId(opportunity_id), creator_id=creator_id)

        payload = serialize_model_for_cli(created)
        return CommandOutput(
            data={"listEntry": payload},
            resolved=resolved_list.resolved,
            api_called=True,
        )

    run_command(ctx, command="list entry add", fn=fn)


@list_entry_group.command(name="delete", cls=RichCommand)
@click.argument("list_selector")
@click.argument("entry_id", type=int)
@output_options
@click.pass_obj
def list_entry_delete(ctx: CLIContext, list_selector: str, entry_id: int) -> None:
    """Delete a list entry (V1 write path)."""

    def fn(ctx: CLIContext, warnings: list[str]) -> CommandOutput:
        client = ctx.get_client(warnings=warnings)
        resolved_list = resolve_list_selector(client=client, selector=list_selector)
        entries = client.lists.entries(resolved_list.list.id)
        success = entries.delete(ListEntryId(entry_id))
        return CommandOutput(
            data={"success": success},
            resolved=resolved_list.resolved,
            api_called=True,
        )

    run_command(ctx, command="list entry delete", fn=fn)


@list_entry_group.command(name="update-field", cls=RichCommand)
@click.argument("list_selector")
@click.argument("entry_id", type=int)
@click.option("--field-id", required=True, help="Field id to update.")
@click.option("--value", default=None, help="New value (string).")
@click.option("--value-json", default=None, help="New value (JSON literal).")
@output_options
@click.pass_obj
def list_entry_update_field(
    ctx: CLIContext,
    list_selector: str,
    entry_id: int,
    *,
    field_id: str,
    value: str | None,
    value_json: str | None,
) -> None:
    """Update a list entry field (V2 write path)."""

    def fn(ctx: CLIContext, warnings: list[str]) -> CommandOutput:
        if value is None and value_json is None:
            raise CLIError(
                "Provide --value or --value-json.",
                error_type="usage_error",
                exit_code=2,
            )
        if value is not None and value_json is not None:
            raise CLIError(
                "Use only one of --value or --value-json.",
                error_type="usage_error",
                exit_code=2,
            )
        client = ctx.get_client(warnings=warnings)
        resolved_list = resolve_list_selector(client=client, selector=list_selector)
        entries = client.lists.entries(resolved_list.list.id)
        parsed_value = value if value_json is None else parse_json_value(value_json, label="value")
        try:
            parsed_field_id: AnyFieldId = FieldId(field_id)
        except ValueError:
            parsed_field_id = EnrichedFieldId(field_id)
        result = entries.update_field_value(ListEntryId(entry_id), parsed_field_id, parsed_value)
        payload = serialize_model_for_cli(result)
        return CommandOutput(
            data={"fieldValues": payload},
            resolved=resolved_list.resolved,
            api_called=True,
        )

    run_command(ctx, command="list entry update-field", fn=fn)


@list_entry_group.command(name="batch-update", cls=RichCommand)
@click.argument("list_selector")
@click.argument("entry_id", type=int)
@click.option(
    "--updates-json",
    required=True,
    help="JSON object of fieldId -> value pairs.",
)
@output_options
@click.pass_obj
def list_entry_batch_update(
    ctx: CLIContext,
    list_selector: str,
    entry_id: int,
    *,
    updates_json: str,
) -> None:
    """Batch update list entry fields (V2 write path)."""

    def fn(ctx: CLIContext, warnings: list[str]) -> CommandOutput:
        client = ctx.get_client(warnings=warnings)
        resolved_list = resolve_list_selector(client=client, selector=list_selector)
        entries = client.lists.entries(resolved_list.list.id)
        parsed = parse_json_value(updates_json, label="updates-json")
        if not isinstance(parsed, dict):
            raise CLIError(
                "--updates-json must be a JSON object.",
                error_type="usage_error",
                exit_code=2,
            )
        result = entries.batch_update_fields(ListEntryId(entry_id), parsed)
        payload = serialize_model_for_cli(result)
        return CommandOutput(
            data={"fieldUpdates": payload},
            resolved=resolved_list.resolved,
            api_called=True,
        )

    run_command(ctx, command="list entry batch-update", fn=fn)
