from __future__ import annotations

import json
import os
import signal
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

        show_progress = (
            ctx.progress != "never"
            and not ctx.quiet
            and (ctx.progress == "always" or sys.stderr.isatty())
        )

        with ExitStack() as stack:
            progress: Progress | None = None
            task_id: TaskID | None = None
            if show_progress:
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
                task_id = progress.add_task("Fetching", total=max_results)

            for page in pages:
                for idx, item in enumerate(page.data):
                    if lt is not None and item.type != lt:
                        continue
                    rows.append(
                        {
                            "id": int(item.id),
                            "name": item.name,
                            "type": ListType(item.type).name.lower(),
                            "ownerId": int(item.owner_id)
                            if getattr(item, "owner_id", None)
                            else None,
                            "isPublic": getattr(item, "is_public", None),
                        }
                    )
                    if progress and task_id is not None:
                        progress.update(task_id, completed=len(rows))
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


ExpandChoice = Literal["people", "companies"]
CsvMode = Literal["flat", "nested"]
ExpandOnError = Literal["raise", "skip"]


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
    help="Use field names or IDs for CSV headers.",
)
@click.option("--csv-bom", is_flag=True, help="Write UTF-8 BOM for Excel.")
@click.option("--dry-run", is_flag=True, help="Validate selectors and print export plan.")
# Expand options (Phase 1)
@click.option(
    "--expand",
    "expand",
    multiple=True,
    type=click.Choice(["people", "companies"]),
    help="Expand associated entities (repeatable). Uses V1 API.",
)
@click.option(
    "--expand-max-results",
    type=int,
    default=100,
    show_default=True,
    help="Max associations per entry per type.",
)
@click.option(
    "--expand-all",
    is_flag=True,
    help="Fetch all associations per entry (no limit).",
)
@click.option(
    "--expand-on-error",
    type=click.Choice(["raise", "skip"]),
    default="raise",
    show_default=True,
    help="How to handle per-entry expansion errors.",
)
@click.option(
    "--csv-mode",
    type=click.Choice(["flat", "nested"]),
    default="flat",
    show_default=True,
    help="CSV expansion format: flat (one row per association) or nested (JSON arrays).",
)
# Phase 4 deferred options (not yet implemented)
@click.option(
    "--expand-fields",
    "expand_fields",
    multiple=True,
    type=str,
    help="[Phase 4] Expand specific field values (not yet implemented).",
)
@click.option(
    "--expand-field-type",
    "expand_field_types",
    multiple=True,
    type=click.Choice(["person", "company", "location", "interaction"]),
    help="[Phase 4] Expand all fields of a given type (not yet implemented).",
)
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
    # Expand options
    expand: tuple[str, ...],
    expand_max_results: int,
    expand_all: bool,
    expand_on_error: str,
    csv_mode: str,
    # Phase 4 deferred options
    expand_fields: tuple[str, ...],
    expand_field_types: tuple[str, ...],
) -> None:
    """
    Export list entries to JSON or CSV.

    LIST_SELECTOR can be a list id or exact list name.

    Examples:

    - `xaffinitylist export "Pipeline" --all`
    - `xaffinitylist export 12345 --csv pipeline.csv --all`
    - `xaffinitylist export "Pipeline" --saved-view "Active Deals" --csv deals.csv`
    - `xaffinitylist export "Pipeline" --field Status --field "Deal Size" --all`
    - `xaffinitylist export "Pipeline" --expand people --all --csv opps-with-people.csv`
    - `xaffinitylist export "Pipeline" --expand people --expand companies --all`
    """

    def fn(ctx: CLIContext, warnings: list[str]) -> CommandOutput:
        # Phase 4 deferred options - fail early with clear message
        if expand_fields:
            raise CLIError(
                "--expand-fields is not yet implemented (planned for Phase 4).",
                exit_code=2,
                error_type="usage_error",
                hint="Use --expand people/companies to expand entity associations.",
            )
        if expand_field_types:
            raise CLIError(
                "--expand-field-type is not yet implemented (planned for Phase 4).",
                exit_code=2,
                error_type="usage_error",
                hint="Use --expand people/companies to expand entity associations.",
            )

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

        # Parse and validate expand options
        expand_set = {e.strip().lower() for e in expand if e and e.strip()}
        want_expand = len(expand_set) > 0

        if want_expand and cursor:
            raise CLIError(
                "--cursor cannot be combined with --expand.",
                exit_code=2,
                error_type="usage_error",
                hint="For large exports, use streaming CSV output or the SDK with checkpointing.",
            )

        # Warn if both --expand-all and --expand-max-results specified
        if expand_all and expand_max_results != 100:
            warnings.append(
                f"--expand-all specified; ignoring --expand-max-results {expand_max_results}"
            )

        # Determine effective expansion limit
        effective_expand_limit: int | None = None if expand_all else expand_max_results

        client = ctx.get_client(warnings=warnings)
        resolved_list = resolve_list_selector(client=client, selector=list_selector)
        list_id = ListId(int(resolved_list.list.id))
        # Note: AffinityModel uses use_enum_values=True, so list.type is an int
        list_type_value = resolved_list.list.type
        list_type = (
            ListType(list_type_value) if isinstance(list_type_value, int) else list_type_value
        )
        resolved: dict[str, Any] = dict(resolved_list.resolved)

        # Validate expand options for list type (Phase 1: opportunity lists only)
        if want_expand:
            valid_expand_for_type: dict[ListType, set[str]] = {
                ListType.OPPORTUNITY: {"people", "companies"},
                # Phase 2+: ListType.PERSON: {"companies"},
                # Phase 2+: ListType.ORGANIZATION: {"people"},
            }
            valid_for_this_type = valid_expand_for_type.get(list_type, set())
            invalid_expands = expand_set - valid_for_this_type

            if invalid_expands:
                if list_type not in valid_expand_for_type:
                    raise CLIError(
                        f"--expand is not yet supported for {list_type.name.lower()} lists.",
                        exit_code=2,
                        error_type="usage_error",
                        hint="Currently only opportunity lists support --expand.",
                    )
                raise CLIError(
                    f"--expand {', '.join(sorted(invalid_expands))} is not valid for "
                    f"{list_type.name.lower()} lists.",
                    exit_code=2,
                    error_type="usage_error",
                    details={"validExpand": sorted(valid_for_this_type)},
                )

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
            data: dict[str, Any] = {
                "listId": int(list_id),
                "listName": resolved_list.list.name,
                "listType": list_type.name.lower(),
                "savedView": saved_view,
                "fieldIds": selected_field_ids,
                "filter": filter_expr,
                "pageSize": page_size,
                "cursor": cursor,
                "csv": str(csv_path) if csv_path else None,
            }
            if want_expand:
                # Estimate API calls for expansion
                entry_count = resolved_list.list.list_size or 0
                expand_calls = entry_count  # 1 call per entry (optimized for dual)
                data["expand"] = sorted(expand_set)
                data["expandMaxResults"] = effective_expand_limit
                data["estimatedEntries"] = entry_count
                data["csvMode"] = csv_mode if csv_path else None
                data["estimatedApiCalls"] = {
                    "listEntries": max(1, entry_count // page_size),
                    "associations": expand_calls,
                    "total": max(1, entry_count // page_size) + expand_calls,
                    "note": (
                        "Using get_associations() optimization "
                        "(both people+companies in 1 call per entry)"
                        if "people" in expand_set and "companies" in expand_set
                        else "1 call per entry"
                    ),
                }
                # Estimate duration based on entry count
                if entry_count <= 50:
                    data["estimatedDuration"] = "~30 seconds to 1 minute"
                elif entry_count <= 150:
                    data["estimatedDuration"] = f"~2-5 minutes for {entry_count} entries"
                elif entry_count <= 500:
                    data["estimatedDuration"] = f"~5-10 minutes for {entry_count} entries"
                else:
                    data["estimatedDuration"] = f"~10-20+ minutes for {entry_count} entries"
                # Add dry run warnings
                dry_run_warnings = []
                dry_run_warnings.append("Expansion uses V1 API which is slower than V2.")
                if effective_expand_limit is not None:
                    dry_run_warnings.append(
                        f"Using --expand-max-results {effective_expand_limit} (default). "
                        "Some entries may have more associations. "
                        "Use --expand-all for complete data."
                    )
                if entry_count > 1000:
                    dry_run_warnings.append(
                        f"Large export ({entry_count} entries) may take 10-15 minutes or more."
                    )
                data["warnings"] = dry_run_warnings
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

        # Helper to format progress description with association counts
        def _format_progress_desc(
            entries: int,
            total: int | None,
            people_count: int,
            companies_count: int,
            expand_set: set[str],
        ) -> str:
            if total and total > 0:
                pct = int(100 * entries / total)
                desc = f"Exporting: {entries}/{total} entries ({pct}%)"
            else:
                desc = f"Exporting: {entries} entries"
            if expand_set:
                parts = []
                if "people" in expand_set and people_count > 0:
                    parts.append(f"{people_count} people")
                if "companies" in expand_set and companies_count > 0:
                    parts.append(f"{companies_count} companies")
                if parts:
                    desc += ", " + " + ".join(parts)
            return desc

        with ExitStack() as stack:
            progress: Progress | None = None
            task_id: TaskID | None = None
            show_progress = (
                ctx.progress != "never"
                and not ctx.quiet
                and (ctx.progress == "always" or sys.stderr.isatty())
            )
            entry_total = resolved_list.list.list_size if want_expand else None
            if show_progress:
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
                initial_desc = (
                    "Exporting"
                    if not want_expand
                    else _format_progress_desc(0, entry_total, 0, 0, expand_set)
                )
                task_id = progress.add_task(
                    initial_desc, total=max_results if max_results else None
                )

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
                base_header = [
                    "listEntryId",
                    "entityType",
                    "entityId",
                    "entityName",
                    *field_headers,
                ]

                # Add expansion columns if needed
                if want_expand:
                    header = _expand_csv_headers(base_header, expand_set, csv_mode)
                else:
                    header = base_header

                pid = os.getpid()
                temp_path = csv_path_obj.with_suffix(f"{csv_path_obj.suffix}.{pid}.tmp")
                csv_iter_state: dict[str, Any] = {}
                entries_with_truncated_assoc: list[int] = []
                skipped_entries: list[int] = []
                entries_with_large_nested_assoc: list[int] = []
                csv_associations_fetched: dict[str, int] = {"people": 0, "companies": 0}
                csv_entries_processed = 0

                def iter_rows() -> Any:
                    nonlocal rows_written, next_cursor, csv_entries_processed
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

                        if not want_expand:
                            # No expansion - yield row as-is
                            rows_written += 1
                            if progress is not None and task_id is not None:
                                progress.update(task_id, completed=rows_written)
                            yield row
                            continue

                        # Handle expansion for opportunity lists
                        entity_id = row.get("entityId")
                        if entity_id is None:
                            # No entity - emit row with empty expansion columns
                            expanded_row = dict(row)
                            expanded_row["expandedType"] = ""
                            expanded_row["expandedId"] = ""
                            expanded_row["expandedName"] = ""
                            if "people" in expand_set:
                                expanded_row["expandedEmail"] = ""
                            if "companies" in expand_set:
                                expanded_row["expandedDomain"] = ""
                            rows_written += 1
                            if progress is not None and task_id is not None:
                                progress.update(task_id, completed=rows_written)
                            yield expanded_row
                            continue

                        # Fetch associations
                        result = _fetch_opportunity_associations(
                            client=client,
                            opportunity_id=OpportunityId(entity_id),
                            expand_set=expand_set,
                            max_results=effective_expand_limit,
                            on_error=expand_on_error,
                            warnings=warnings,
                        )

                        if result is None:
                            # Error occurred and on_error='skip'
                            skipped_entries.append(entity_id)
                            continue

                        people, companies = result
                        csv_entries_processed += 1
                        csv_associations_fetched["people"] += len(people)
                        csv_associations_fetched["companies"] += len(companies)

                        # Update progress description with association counts
                        if progress is not None and task_id is not None:
                            progress.update(
                                task_id,
                                description=_format_progress_desc(
                                    csv_entries_processed,
                                    entry_total,
                                    csv_associations_fetched["people"],
                                    csv_associations_fetched["companies"],
                                    expand_set,
                                ),
                            )

                        # Check for truncation
                        if effective_expand_limit is not None and (
                            len(people) >= effective_expand_limit
                            or len(companies) >= effective_expand_limit
                        ):
                            entries_with_truncated_assoc.append(entity_id)

                        # Handle CSV mode
                        if csv_mode == "flat":
                            # Flat mode: one row per association
                            emitted_any = False

                            # Emit person rows
                            for person in people:
                                expanded_row = dict(row)
                                expanded_row["expandedType"] = "person"
                                expanded_row["expandedId"] = person["id"]
                                expanded_row["expandedName"] = person["name"]
                                if "people" in expand_set:
                                    expanded_row["expandedEmail"] = person.get("primaryEmail") or ""
                                if "companies" in expand_set:
                                    expanded_row["expandedDomain"] = ""
                                rows_written += 1
                                emitted_any = True
                                if progress is not None and task_id is not None:
                                    progress.update(task_id, completed=rows_written)
                                yield expanded_row

                            # Emit company rows
                            for company in companies:
                                expanded_row = dict(row)
                                expanded_row["expandedType"] = "company"
                                expanded_row["expandedId"] = company["id"]
                                expanded_row["expandedName"] = company["name"]
                                if "people" in expand_set:
                                    expanded_row["expandedEmail"] = ""
                                if "companies" in expand_set:
                                    expanded_row["expandedDomain"] = company.get("domain") or ""
                                rows_written += 1
                                emitted_any = True
                                if progress is not None and task_id is not None:
                                    progress.update(task_id, completed=rows_written)
                                yield expanded_row

                            # If no associations, emit one row with empty expansion columns
                            if not emitted_any:
                                expanded_row = dict(row)
                                expanded_row["expandedType"] = ""
                                expanded_row["expandedId"] = ""
                                expanded_row["expandedName"] = ""
                                if "people" in expand_set:
                                    expanded_row["expandedEmail"] = ""
                                if "companies" in expand_set:
                                    expanded_row["expandedDomain"] = ""
                                rows_written += 1
                                if progress is not None and task_id is not None:
                                    progress.update(task_id, completed=rows_written)
                                yield expanded_row

                        else:
                            # Nested mode: JSON arrays in columns
                            total_assoc = len(people) + len(companies)
                            if total_assoc > 100:
                                entries_with_large_nested_assoc.append(entity_id)
                            expanded_row = dict(row)
                            if "people" in expand_set:
                                people_json = json.dumps(people) if people else "[]"
                                expanded_row["_expand_people"] = people_json
                            if "companies" in expand_set:
                                companies_json = json.dumps(companies) if companies else "[]"
                                expanded_row["_expand_companies"] = companies_json
                            rows_written += 1
                            if progress is not None and task_id is not None:
                                progress.update(task_id, completed=rows_written)
                            yield expanded_row

                # Set up interrupt handler to notify user of partial results
                original_handler = signal.getsignal(signal.SIGINT)

                def _interrupt_handler(_signum: int, _frame: Any) -> None:
                    # Re-raise to stop the iteration
                    raise KeyboardInterrupt()

                try:
                    signal.signal(signal.SIGINT, _interrupt_handler)
                    write_result = write_csv(
                        path=temp_path,
                        rows=iter_rows(),
                        fieldnames=header,
                        bom=csv_bom,
                    )
                    temp_path.replace(csv_path_obj)
                except KeyboardInterrupt:
                    # Print interrupt notification with partial file info
                    Console(file=sys.stderr).print(
                        f"\nInterrupted. Partial results in: {temp_path} "
                        f"({rows_written} rows written)"
                    )
                    sys.exit(130)
                finally:
                    signal.signal(signal.SIGINT, original_handler)

                # Add truncation warning if any entries were truncated
                if entries_with_truncated_assoc:
                    count = len(entries_with_truncated_assoc)
                    warnings.append(
                        f"{count} entries had associations truncated at {effective_expand_limit} "
                        "(use --expand-all for complete data)"
                    )

                # Add memory warning for large nested arrays
                if entries_with_large_nested_assoc and csv_mode == "nested":
                    count = len(entries_with_large_nested_assoc)
                    first_id = entries_with_large_nested_assoc[0]
                    warnings.append(
                        f"{count} entries have >100 associations. "
                        f"Large nested arrays may impact memory (e.g., entry {first_id}). "
                        "Consider --csv-mode flat."
                    )

                # Add skipped entries summary with IDs
                if skipped_entries:
                    if len(skipped_entries) <= 10:
                        ids_str = ", ".join(str(eid) for eid in skipped_entries)
                        warnings.append(
                            f"{len(skipped_entries)} entries skipped due to errors: {ids_str} "
                            "(use --expand-on-error raise to fail on errors)"
                        )
                    else:
                        first_ids = ", ".join(str(eid) for eid in skipped_entries[:5])
                        warnings.append(
                            f"{len(skipped_entries)} entries skipped due to errors "
                            f"(first 5: {first_ids}, ...) "
                            "(use --expand-on-error raise to fail on errors)"
                        )

                csv_ref, csv_is_relative = artifact_path(csv_path_obj)
                csv_data: dict[str, Any] = {
                    "listId": int(list_id),
                    "rowsWritten": rows_written,
                    "csv": csv_ref,
                }
                if want_expand:
                    csv_data["entriesProcessed"] = csv_entries_processed + len(skipped_entries)
                    csv_data["associationsFetched"] = {
                        k: v for k, v in csv_associations_fetched.items() if k in expand_set
                    }
                if csv_iter_state.get("truncatedMidPage") is True:
                    warnings.append(
                        "Results truncated mid-page; resume cursor omitted "
                        "to avoid skipping items. Re-run with a higher "
                        "--max-results or without it to paginate safely."
                    )
                return CommandOutput(
                    data=csv_data,
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
            # Emit memory warning for large JSON exports with expansion
            if want_expand:
                entry_count = resolved_list.list.list_size or 0
                # Rough estimate: each entry with associations is ~1KB
                estimated_rows = entry_count
                if estimated_rows > 1000:
                    warnings.append(
                        f"JSON output will buffer ~{estimated_rows} rows in memory. "
                        "For large exports, consider --csv for streaming output."
                    )

            rows: list[dict[str, Any]] = []
            table_iter_state: dict[str, Any] = {}
            json_entries_with_truncated_assoc: list[int] = []
            json_skipped_entries: list[int] = []
            associations_fetched: dict[str, int] = {"people": 0, "companies": 0}

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

                if not want_expand:
                    rows.append(row)
                    if progress is not None and task_id is not None:
                        progress.update(task_id, completed=len(rows))
                    continue

                # Handle expansion for JSON output (nested arrays)
                entity_id = row.get("entityId")
                if entity_id is None:
                    # No entity - add row with empty arrays
                    expanded_row = dict(row)
                    if "people" in expand_set:
                        expanded_row["people"] = []
                    if "companies" in expand_set:
                        expanded_row["companies"] = []
                    expanded_row["associations"] = "—"
                    rows.append(expanded_row)
                    if progress is not None and task_id is not None:
                        progress.update(task_id, completed=len(rows))
                    continue

                # Fetch associations
                result = _fetch_opportunity_associations(
                    client=client,
                    opportunity_id=OpportunityId(entity_id),
                    expand_set=expand_set,
                    max_results=effective_expand_limit,
                    on_error=expand_on_error,
                    warnings=warnings,
                )

                if result is None:
                    # Error occurred and on_error='skip' - skip this entry entirely
                    json_skipped_entries.append(entity_id)
                    continue

                people, companies = result

                # Check for truncation
                if effective_expand_limit is not None and (
                    len(people) >= effective_expand_limit
                    or len(companies) >= effective_expand_limit
                ):
                    json_entries_with_truncated_assoc.append(entity_id)

                # Track counts
                associations_fetched["people"] += len(people)
                associations_fetched["companies"] += len(companies)

                # Update progress description with association counts
                if progress is not None and task_id is not None:
                    progress.update(
                        task_id,
                        description=_format_progress_desc(
                            len(rows) + 1,  # +1 for current entry being processed
                            entry_total,
                            associations_fetched["people"],
                            associations_fetched["companies"],
                            expand_set,
                        ),
                    )

                # Add nested arrays to row
                expanded_row = dict(row)
                if "people" in expand_set:
                    expanded_row["people"] = people
                if "companies" in expand_set:
                    expanded_row["companies"] = companies

                # Add associations summary for table mode
                summary_parts = []
                if "people" in expand_set:
                    pc = len(people)
                    if pc > 0:
                        label = "+ people" if pc >= 100 else " person" if pc == 1 else " people"
                        summary_parts.append(f"{pc}{label}")
                if "companies" in expand_set:
                    cc = len(companies)
                    if cc > 0:
                        if cc >= 100:
                            label = "+ companies"
                        elif cc == 1:
                            label = " company"
                        else:
                            label = " companies"
                        summary_parts.append(f"{cc}{label}")
                assoc_summary = ", ".join(summary_parts) if summary_parts else "—"
                expanded_row["associations"] = assoc_summary

                rows.append(expanded_row)
                if progress is not None and task_id is not None:
                    progress.update(task_id, completed=len(rows))

            if table_iter_state.get("truncatedMidPage") is True:
                warnings.append(
                    "Results truncated mid-page; resume cursor omitted "
                    "to avoid skipping items. Re-run with a higher "
                    "--max-results or without it to paginate safely."
                )

            # Add truncation warning for JSON output
            if json_entries_with_truncated_assoc:
                count = len(json_entries_with_truncated_assoc)
                warnings.append(
                    f"{count} entries had associations truncated at {effective_expand_limit} "
                    "(use --expand-all for complete data)"
                )

            # Add skipped entries summary for JSON output with IDs
            if json_skipped_entries:
                if len(json_skipped_entries) <= 10:
                    ids_str = ", ".join(str(eid) for eid in json_skipped_entries)
                    warnings.append(
                        f"{len(json_skipped_entries)} entries skipped due to errors: {ids_str} "
                        "(use --expand-on-error raise to fail on errors)"
                    )
                else:
                    first_ids = ", ".join(str(eid) for eid in json_skipped_entries[:5])
                    warnings.append(
                        f"{len(json_skipped_entries)} entries skipped due to errors "
                        f"(first 5: {first_ids}, ...) "
                        "(use --expand-on-error raise to fail on errors)"
                    )

            # Build output data
            output_data: dict[str, Any] = {"rows": rows}
            if want_expand:
                output_data["entriesProcessed"] = len(rows) + len(json_skipped_entries)
                output_data["associationsFetched"] = {
                    k: v for k, v in associations_fetched.items() if k in expand_set
                }

            return CommandOutput(
                data=output_data,
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


def _fetch_opportunity_associations(
    client: Any,
    opportunity_id: OpportunityId,
    *,
    expand_set: set[str],
    max_results: int | None,
    on_error: str,
    warnings: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]] | None:
    """
    Fetch people and/or companies associated with an opportunity.

    Returns:
        Tuple of (people_list, companies_list) where each list contains dicts with
        id, name, primaryEmail/domain. Returns None if error occurred and on_error='skip'.
    """
    want_people = "people" in expand_set
    want_companies = "companies" in expand_set

    people: list[dict[str, Any]] = []
    companies: list[dict[str, Any]] = []

    try:
        # Use dual optimization if both are requested
        if want_people and want_companies:
            assoc = client.opportunities.get_associations(opportunity_id)
            person_ids = [int(pid) for pid in assoc.person_ids]
            company_ids = [int(cid) for cid in assoc.company_ids]
        else:
            person_ids = []
            company_ids = []
            if want_people:
                person_ids = [
                    int(pid)
                    for pid in client.opportunities.get_associated_person_ids(opportunity_id)
                ]
            if want_companies:
                company_ids = [
                    int(cid)
                    for cid in client.opportunities.get_associated_company_ids(opportunity_id)
                ]

        # Fetch people details
        if want_people and person_ids:
            fetched_people = client.opportunities.get_associated_people(
                opportunity_id, max_results=max_results
            )
            people = [
                {
                    "id": int(p.id),
                    "name": p.full_name,
                    # V1 API doesn't return primary_email, fall back to first email
                    "primaryEmail": p.primary_email or (p.emails[0] if p.emails else None),
                }
                for p in fetched_people
            ]

        # Fetch company details
        if want_companies and company_ids:
            fetched_companies = client.opportunities.get_associated_companies(
                opportunity_id, max_results=max_results
            )
            companies = [
                {
                    "id": int(c.id),
                    "name": c.name,
                    "domain": c.domain,
                }
                for c in fetched_companies
            ]

    except Exception as e:
        if on_error == "skip":
            warnings.append(f"Skipped expansion for opportunity {int(opportunity_id)}: {e}")
            return None
        raise

    return people, companies


def _expand_csv_headers(
    base_headers: list[str],
    expand_set: set[str],
    csv_mode: str = "flat",
) -> list[str]:
    """
    Add expansion columns to CSV headers.

    Flat mode: expandedType, expandedId, expandedName, expandedEmail, expandedDomain
    Nested mode: _expand_people, _expand_companies (JSON arrays)
    """
    headers = list(base_headers)
    if csv_mode == "nested":
        # Nested mode: add JSON array columns
        if "people" in expand_set:
            headers.append("_expand_people")
        if "companies" in expand_set:
            headers.append("_expand_companies")
    else:
        # Flat mode: add row-per-association columns
        headers.append("expandedType")
        headers.append("expandedId")
        headers.append("expandedName")
        if "people" in expand_set:
            headers.append("expandedEmail")
        if "companies" in expand_set:
            headers.append("expandedDomain")
    return headers


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
