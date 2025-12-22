from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from affinity.models.entities import Company, CompanyCreate, CompanyUpdate
from affinity.models.types import FieldId
from affinity.types import CompanyId, FieldType, ListId, PersonId

from ..click_compat import RichCommand, RichGroup, click
from ..context import CLIContext
from ..errors import CLIError
from ..options import output_options
from ..progress import ProgressManager, ProgressSettings
from ..resolve import resolve_list_selector
from ..runner import CommandOutput, run_command
from ._entity_files_dump import dump_entity_files_bundle
from ._list_entry_fields import (
    ListEntryFieldsScope,
    build_list_entry_field_rows,
    filter_list_entry_fields,
)
from .resolve_url_cmd import _parse_affinity_url


@click.group(name="company", cls=RichGroup)
def company_group() -> None:
    """Company commands."""


@company_group.command(name="search", cls=RichCommand)
@click.argument("query")
@click.option("--page-size", type=int, default=None, help="Page size (max 500).")
@click.option("--cursor", type=str, default=None, help="Resume from a prior cursor.")
@click.option("--max-results", type=int, default=None, help="Stop after N results total.")
@click.option("--all", "all_pages", is_flag=True, help="Fetch all pages.")
@click.option(
    "--with-interaction-dates",
    is_flag=True,
    default=False,
    help="Include interaction date data.",
)
@click.option(
    "--with-interaction-persons",
    is_flag=True,
    default=False,
    help="Include persons for interactions.",
)
@click.option(
    "--with-opportunities",
    is_flag=True,
    default=False,
    help="Include associated opportunity IDs.",
)
@output_options
@click.pass_obj
def company_search(
    ctx: CLIContext,
    query: str,
    *,
    page_size: int | None,
    cursor: str | None,
    max_results: int | None,
    all_pages: bool,
    with_interaction_dates: bool,
    with_interaction_persons: bool,
    with_opportunities: bool,
) -> None:
    """
    Search companies by name or domain.

    `QUERY` is a free-text term passed to Affinity's company search. Typical inputs:

    - Domain: `longevitix.co`
    - Company name: `Longevitix`

    Examples:

    - `affinity company search longevitix`
    - `affinity company search longevitix.co`
    - `affinity company search longevitix --with-interaction-dates`
    """

    def fn(ctx: CLIContext, warnings: list[str]) -> CommandOutput:
        client = ctx.get_client(warnings=warnings)
        results: list[dict[str, object]] = []
        first_page = True
        for page in client.companies.search_pages(
            query,
            with_interaction_dates=with_interaction_dates,
            with_interaction_persons=with_interaction_persons,
            with_opportunities=with_opportunities,
            page_size=page_size,
            page_token=cursor,
        ):
            for idx, company in enumerate(page.data):
                results.append(_company_row(company))
                if max_results is not None and len(results) >= max_results:
                    stopped_mid_page = idx < (len(page.data) - 1)
                    if stopped_mid_page:
                        warnings.append(
                            "Results truncated mid-page; resume cursor omitted "
                            "to avoid skipping items. Re-run with a higher "
                            "--max-results or without it to paginate safely."
                        )
                    return CommandOutput(
                        data={"companies": results[:max_results]},
                        pagination={
                            "companies": {
                                "nextCursor": page.next_page_token,
                                "prevCursor": None,
                            }
                        }
                        if page.next_page_token and not stopped_mid_page
                        else None,
                        api_called=True,
                    )

            if first_page and not all_pages and max_results is None:
                return CommandOutput(
                    data={"companies": results},
                    pagination={
                        "companies": {"nextCursor": page.next_page_token, "prevCursor": None}
                    }
                    if page.next_page_token
                    else None,
                    api_called=True,
                )
            first_page = False

        return CommandOutput(data={"companies": results}, pagination=None, api_called=True)

    run_command(ctx, command="company search", fn=fn)


def _parse_field_types(values: tuple[str, ...]) -> list[FieldType] | None:
    """Parse --field-type option values to FieldType enums."""
    if not values:
        return None
    result: list[FieldType] = []
    valid_types = {ft.value.lower(): ft for ft in FieldType}
    for v in values:
        lower = v.lower()
        if lower not in valid_types:
            raise CLIError(
                f"Unknown field type: {v}",
                exit_code=2,
                error_type="usage_error",
                hint=f"Valid types: {', '.join(sorted(valid_types.keys()))}",
            )
        result.append(valid_types[lower])
    return result


@company_group.command(name="ls", cls=RichCommand)
@click.option("--page-size", type=int, default=None, help="Page size (limit).")
@click.option("--cursor", type=str, default=None, help="Resume from a prior cursor.")
@click.option("--max-results", type=int, default=None, help="Stop after N items total.")
@click.option("--all", "all_pages", is_flag=True, help="Fetch all pages.")
@click.option(
    "--field",
    "field_ids",
    type=str,
    multiple=True,
    help="Field ID or name to include (repeatable).",
)
@click.option(
    "--field-type",
    "field_types",
    type=str,
    multiple=True,
    help="Field type to include (repeatable). Values: global, enriched, relationship-intelligence.",
)
@click.option(
    "--filter",
    "filter_expr",
    type=str,
    default=None,
    help='V2 filter expression (e.g., \'field("Industry").equals("Software")\').',
)
@output_options
@click.pass_obj
def company_ls(
    ctx: CLIContext,
    *,
    page_size: int | None,
    cursor: str | None,
    max_results: int | None,
    all_pages: bool,
    field_ids: tuple[str, ...],
    field_types: tuple[str, ...],
    filter_expr: str | None,
) -> None:
    """
    List companies with V2 pagination.

    Supports field selection, field types, and V2 filter expressions.

    Examples:

    - `affinity company ls`
    - `affinity company ls --page-size 50`
    - `affinity company ls --field-type enriched --all`
    - `affinity company ls --filter 'field("Industry").equals("Software")'`
    """

    def fn(ctx: CLIContext, warnings: list[str]) -> CommandOutput:
        client = ctx.get_client(warnings=warnings)

        if cursor is not None and page_size is not None:
            raise CLIError(
                "--cursor cannot be combined with --page-size.",
                exit_code=2,
                error_type="usage_error",
            )

        parsed_field_types = _parse_field_types(field_types)
        parsed_field_ids: list[FieldId] | None = (
            [FieldId(fid) for fid in field_ids] if field_ids else None
        )

        rows: list[dict[str, object]] = []
        first_page = True

        pages_iter = client.companies.pages(
            field_ids=parsed_field_ids,
            field_types=parsed_field_types,
            filter=filter_expr,
            limit=page_size,
            cursor=cursor,
        )

        for page in pages_iter:
            for idx, company in enumerate(page.data):
                rows.append(_company_ls_row(company))
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
                            "companies": {
                                "nextCursor": page.pagination.next_cursor,
                                "prevCursor": page.pagination.prev_cursor,
                            }
                        }
                    return CommandOutput(
                        data={"companies": rows[:max_results]},
                        pagination=pagination,
                        api_called=True,
                    )

            if first_page and not all_pages and max_results is None:
                return CommandOutput(
                    data={"companies": rows},
                    pagination=(
                        {
                            "companies": {
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

        return CommandOutput(data={"companies": rows}, pagination=None, api_called=True)

    run_command(ctx, command="company ls", fn=fn)


def _company_ls_row(company: Company) -> dict[str, object]:
    """Build a row for company ls output."""
    return {
        "id": int(company.id),
        "name": company.name,
        "domain": company.domain,
        "domains": company.domains,
    }


def _company_row(company: Company) -> dict[str, object]:
    last_interaction = None
    if company.interaction_dates is not None:
        last_interaction = company.interaction_dates.last_interaction_date
    return {
        "id": int(company.id),
        "name": company.name,
        "domain": company.domain,
        "domains": company.domains,
        "lastInteractionDate": last_interaction,
    }


_COMPANY_FIELDS_ALL_TYPES: tuple[str, ...] = (
    FieldType.GLOBAL.value,
    FieldType.ENRICHED.value,
    FieldType.RELATIONSHIP_INTELLIGENCE.value,
)


def _strip_wrapping_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _resolve_company_selector(*, client: Any, selector: str) -> tuple[CompanyId, dict[str, Any]]:
    raw = selector.strip()
    if raw.isdigit():
        company_id = CompanyId(int(raw))
        return company_id, {
            "company": {"input": selector, "companyId": int(company_id), "source": "id"}
        }

    if raw.startswith(("http://", "https://")):
        resolved = _parse_affinity_url(raw)
        if resolved.type != "company" or resolved.company_id is None:
            raise CLIError(
                "Expected a company URL like https://<tenant>.affinity.(co|com)/companies/<id>",
                exit_code=2,
                error_type="usage_error",
                details={"input": selector, "resolvedType": resolved.type},
            )
        company_id = CompanyId(int(resolved.company_id))
        return company_id, {
            "company": {
                "input": selector,
                "companyId": int(company_id),
                "source": "url",
                "canonicalUrl": f"https://app.affinity.co/companies/{int(company_id)}",
            }
        }

    lowered = raw.lower()
    if lowered.startswith("domain:"):
        domain = _strip_wrapping_quotes(raw.split(":", 1)[1])
        company_id = _resolve_company_by_domain(client=client, domain=domain)
        return company_id, {
            "company": {
                "input": selector,
                "companyId": int(company_id),
                "source": "domain",
                "domain": domain,
            }
        }

    if lowered.startswith("name:"):
        name = _strip_wrapping_quotes(raw.split(":", 1)[1])
        company_id = _resolve_company_by_name(client=client, name=name)
        return company_id, {
            "company": {
                "input": selector,
                "companyId": int(company_id),
                "source": "name",
                "name": name,
            }
        }

    raise CLIError(
        "Unrecognized company selector.",
        exit_code=2,
        error_type="usage_error",
        hint='Use a numeric id, an Affinity URL, or "domain:<x>" / "name:<x>".',
        details={"input": selector},
    )


def _resolve_company_by_domain(*, client: Any, domain: str) -> CompanyId:
    domain = domain.strip()
    if not domain:
        raise CLIError("Domain cannot be empty.", exit_code=2, error_type="usage_error")

    matches: list[Company] = []
    domain_lower = domain.lower()

    for page in client.companies.search_pages(domain, page_size=500):
        for company in page.data:
            domains: list[str] = []
            if company.domain:
                domains.append(company.domain)
            domains.extend(company.domains or [])
            if any(d.lower() == domain_lower for d in domains):
                matches.append(company)
                if len(matches) >= 20:
                    break
        if len(matches) >= 20 or not page.next_page_token:
            break

    if not matches:
        raise CLIError(
            f'Company not found for domain "{domain}"',
            exit_code=4,
            error_type="not_found",
            hint=f'Run `affinity company search "{domain}"` to explore matches.',
            details={"domain": domain},
        )
    if len(matches) > 1:
        raise CLIError(
            f'Ambiguous company domain "{domain}" ({len(matches)} matches)',
            exit_code=2,
            error_type="ambiguous_resolution",
            details={
                "domain": domain,
                "matches": [
                    {"companyId": int(c.id), "name": c.name, "domain": c.domain}
                    for c in matches[:20]
                ],
            },
        )
    return CompanyId(int(matches[0].id))


def _resolve_company_by_name(*, client: Any, name: str) -> CompanyId:
    name = name.strip()
    if not name:
        raise CLIError("Name cannot be empty.", exit_code=2, error_type="usage_error")

    matches: list[Company] = []
    name_lower = name.lower()

    for page in client.companies.search_pages(name, page_size=500):
        for company in page.data:
            if company.name.lower() == name_lower:
                matches.append(company)
                if len(matches) >= 20:
                    break
        if len(matches) >= 20 or not page.next_page_token:
            break

    if not matches:
        raise CLIError(
            f'Company not found for name "{name}"',
            exit_code=4,
            error_type="not_found",
            hint=f'Run `affinity company search "{name}"` to explore matches.',
            details={"name": name},
        )
    if len(matches) > 1:
        raise CLIError(
            f'Ambiguous company name "{name}" ({len(matches)} matches)',
            exit_code=2,
            error_type="ambiguous_resolution",
            details={
                "name": name,
                "matches": [
                    {"companyId": int(c.id), "name": c.name, "domain": c.domain}
                    for c in matches[:20]
                ],
            },
        )
    return CompanyId(int(matches[0].id))


def _resolve_company_field_ids(
    *,
    client: Any,
    fields: tuple[str, ...],
    field_types: list[str],
) -> tuple[list[str], dict[str, Any]]:
    meta = client.companies.get_fields()
    field_by_id: dict[str, Any] = {str(f.id): f for f in meta}
    by_name: dict[str, list[str]] = {}
    for f in meta:
        by_name.setdefault(str(f.name).lower(), []).append(str(f.id))

    resolved_fields: list[str] = []
    for raw in fields:
        text = _strip_wrapping_quotes(str(raw)).strip()
        if not text:
            continue
        if text in field_by_id:
            resolved_fields.append(text)
            continue
        name_matches = by_name.get(text.lower(), [])
        if len(name_matches) == 1:
            resolved_fields.append(name_matches[0])
            continue
        if len(name_matches) > 1:
            raise CLIError(
                f'Ambiguous field name "{text}" ({len(name_matches)} matches)',
                exit_code=2,
                error_type="ambiguous_resolution",
                details={
                    "name": text,
                    "matches": [
                        {
                            "fieldId": fid,
                            "name": getattr(field_by_id.get(fid), "name", None),
                            "type": getattr(field_by_id.get(fid), "type", None),
                            "valueType": getattr(field_by_id.get(fid), "value_type", None),
                        }
                        for fid in name_matches[:20]
                    ],
                },
            )

        raise CLIError(
            f'Unknown field: "{text}"',
            exit_code=2,
            error_type="usage_error",
            hint="Tip: run `affinity company get <id> --all-fields --json` and inspect "
            "`data.company.fields[*].id` / `data.company.fields[*].name`.",
            details={"field": text},
        )

    expanded: list[str] = []
    for field_type in field_types:
        wanted = field_type.strip()
        if not wanted:
            continue
        candidates = [f for f in meta if f.type == wanted]
        candidates.sort(
            key=lambda f: (
                str(f.name).lower(),
                str(f.id),
            )
        )
        expanded.extend([str(f.id) for f in candidates])

    ordered: list[str] = []
    seen: set[str] = set()
    for fid in [*resolved_fields, *expanded]:
        if fid in seen:
            continue
        ordered.append(fid)
        seen.add(fid)

    resolved_info = {
        "fieldIds": ordered,
        "fieldTypes": field_types,
        "explicitFields": list(fields),
    }
    return ordered, resolved_info


@company_group.group(name="files", cls=RichGroup)
def company_files_group() -> None:
    """Company files."""


@company_files_group.command(name="dump", cls=RichCommand)
@click.argument("company_id", type=int)
@click.option("--out", "out_dir", type=click.Path(), default=None)
@click.option("--overwrite", is_flag=True, help="Overwrite existing files.")
@click.option("--concurrency", type=int, default=3, show_default=True)
@click.option("--page-size", type=int, default=200, show_default=True)
@click.option("--max-files", type=int, default=None, help="Stop after N files.")
@output_options
@click.pass_obj
def company_files_dump(
    ctx: CLIContext,
    company_id: int,
    *,
    out_dir: str | None,
    overwrite: bool,
    concurrency: int,
    page_size: int,
    max_files: int | None,
) -> None:
    def fn(ctx: CLIContext, warnings: list[str]) -> CommandOutput:
        return asyncio.run(
            dump_entity_files_bundle(
                ctx=ctx,
                warnings=warnings,
                out_dir=out_dir,
                overwrite=overwrite,
                concurrency=concurrency,
                page_size=page_size,
                max_files=max_files,
                default_dirname=f"affinity-company-{company_id}-files",
                manifest_entity={"type": "company", "companyId": company_id},
                files_list_kwargs={"company_id": CompanyId(company_id)},
            )
        )

    run_command(ctx, command="company files dump", fn=fn)


@company_files_group.command(name="upload", cls=RichCommand)
@click.argument("company_id", type=int)
@click.option(
    "--file",
    "file_paths",
    type=click.Path(exists=False),
    multiple=True,
    required=True,
    help="File path to upload (repeatable).",
)
@output_options
@click.pass_obj
def company_files_upload(
    ctx: CLIContext,
    company_id: int,
    *,
    file_paths: tuple[str, ...],
) -> None:
    """
    Upload files to a company.

    Examples:

    - `affinity company files upload 123 --file doc.pdf`
    - `affinity company files upload 123 --file a.pdf --file b.pdf`
    """

    def fn(ctx: CLIContext, warnings: list[str]) -> CommandOutput:
        client = ctx.get_client(warnings=warnings)

        # Validate all file paths first
        paths: list[Path] = []
        for fp in file_paths:
            p = Path(fp)
            if not p.exists():
                raise CLIError(
                    f"File not found: {fp}",
                    exit_code=2,
                    error_type="usage_error",
                    hint="Check the file path and try again.",
                )
            if not p.is_file():
                raise CLIError(
                    f"Not a regular file: {fp}",
                    exit_code=2,
                    error_type="usage_error",
                    hint="Only regular files can be uploaded, not directories.",
                )
            paths.append(p)

        results: list[dict[str, object]] = []
        settings = ProgressSettings(mode=ctx.progress, quiet=ctx.quiet)

        with ProgressManager(settings=settings) as pm:
            for p in paths:
                file_size = p.stat().st_size
                _task_id, cb = pm.task(
                    description=f"upload {p.name}",
                    total_bytes=file_size,
                )
                success = client.files.upload_path(
                    p,
                    company_id=CompanyId(company_id),
                    on_progress=cb,
                )
                results.append(
                    {
                        "file": str(p),
                        "filename": p.name,
                        "size": file_size,
                        "success": success,
                    }
                )

        return CommandOutput(
            data={"uploads": results, "companyId": company_id},
            api_called=True,
        )

    run_command(ctx, command="company files upload", fn=fn)


@company_group.command(name="get", cls=RichCommand)
@click.argument("company_selector")
@click.option(
    "-f",
    "--field",
    "fields",
    multiple=True,
    help="Field id or exact field name (repeatable).",
)
@click.option(
    "-t",
    "--field-type",
    "field_types",
    multiple=True,
    type=click.Choice(list(_COMPANY_FIELDS_ALL_TYPES)),
    help="Include all fields of this type (repeatable).",
)
@click.option(
    "--all-fields",
    is_flag=True,
    help="Include all supported (non-list-specific) field data.",
)
@click.option("--no-fields", is_flag=True, help="Do not request field data.")
@click.option(
    "--expand",
    "expand",
    multiple=True,
    type=click.Choice(["lists", "list-entries", "people"]),
    help="Include related data (repeatable).",
)
@click.option(
    "--list",
    "list_selector",
    type=str,
    default=None,
    help=(
        "Filter list-entries expansion to a list id or exact list name "
        "(requires --expand list-entries)."
    ),
)
@click.option(
    "--list-entry-field",
    "list_entry_fields",
    multiple=True,
    help=(
        "Project a list-entry field into its own column (repeatable; requires --expand "
        "list-entries)."
    ),
)
@click.option(
    "--show-list-entry-fields",
    "show_list_entry_fields",
    is_flag=True,
    help=(
        "Render per-list-entry Fields tables in human output (requires --expand list-entries "
        "and --max-results <= 3)."
    ),
)
@click.option(
    "--list-entry-fields-scope",
    "list_entry_fields_scope",
    type=click.Choice(["list-only", "all"]),
    default="list-only",
    show_default=True,
    help="Control which fields appear in list entry tables (human output only).",
)
@click.option(
    "--max-results",
    type=int,
    default=None,
    help="Maximum items to fetch per expansion section (applies to --expand).",
)
@click.option(
    "--all",
    "all_pages",
    is_flag=True,
    help="Fetch all pages for expansions (still capped by --max-results if set).",
)
@output_options
@click.pass_obj
def company_get(
    ctx: CLIContext,
    company_selector: str,
    *,
    fields: tuple[str, ...],
    field_types: tuple[str, ...],
    all_fields: bool,
    no_fields: bool,
    expand: tuple[str, ...],
    list_selector: str | None,
    list_entry_fields: tuple[str, ...],
    show_list_entry_fields: bool,
    list_entry_fields_scope: ListEntryFieldsScope,
    max_results: int | None,
    all_pages: bool,
) -> None:
    """
    Get a company by id, URL, or resolver selector.

    Examples:
    - `affinity company get 223384905`
    - `affinity company get https://mydomain.affinity.com/companies/223384905`
    - `affinity company get domain:acme.com`
    - `affinity company get name:\"Acme Inc\"`
    """

    def fn(ctx: CLIContext, warnings: list[str]) -> CommandOutput:
        client = ctx.get_client(warnings=warnings)
        company_id, resolved = _resolve_company_selector(client=client, selector=company_selector)

        expand_set = {e.strip() for e in expand if e and e.strip()}
        effective_list_entry_fields = tuple(list_entry_fields)
        effective_show_list_entry_fields = bool(show_list_entry_fields)
        effective_list_entry_fields_scope: ListEntryFieldsScope = list_entry_fields_scope
        if ctx.output == "json":
            # These flags are human/table presentation features; keep JSON stable and full-fidelity.
            effective_list_entry_fields = ()
            effective_show_list_entry_fields = False
            effective_list_entry_fields_scope = "all"

        scope_source = None
        click_ctx = click.get_current_context(silent=True)
        if click_ctx is not None:
            get_source = getattr(cast(Any, click_ctx), "get_parameter_source", None)
            if callable(get_source):
                scope_source = get_source("list_entry_fields_scope")
        source_enum = getattr(cast(Any, click.core), "ParameterSource", None)
        default_source = getattr(source_enum, "DEFAULT", None) if source_enum else None
        if (
            ctx.output != "json"
            and scope_source is not None
            and default_source is not None
            and scope_source != default_source
            and not show_list_entry_fields
        ):
            raise CLIError(
                "--list-entry-fields-scope requires --show-list-entry-fields.",
                exit_code=2,
                error_type="usage_error",
            )

        if list_selector and "list-entries" not in expand_set:
            raise CLIError(
                "--list requires --expand list-entries.",
                exit_code=2,
                error_type="usage_error",
                details={"list": list_selector, "expand": sorted(expand_set)},
            )

        if no_fields and (fields or field_types or all_fields):
            raise CLIError(
                "--no-fields cannot be combined with --field/--field-type/--all-fields.",
                exit_code=2,
                error_type="usage_error",
            )

        if (
            effective_list_entry_fields or effective_show_list_entry_fields
        ) and "list-entries" not in expand_set:
            raise CLIError(
                "--list-entry-field/--show-list-entry-fields requires --expand list-entries.",
                exit_code=2,
                error_type="usage_error",
            )

        if effective_list_entry_fields and effective_show_list_entry_fields:
            raise CLIError(
                "--list-entry-field and --show-list-entry-fields are mutually exclusive.",
                exit_code=2,
                error_type="usage_error",
            )

        if effective_show_list_entry_fields:
            if max_results is None:
                raise CLIError(
                    "--show-list-entry-fields requires --max-results N (N <= 3).",
                    exit_code=2,
                    error_type="usage_error",
                    hint=(
                        "Add --max-results 3 to limit output, or use --json / --list-entry-field "
                        "for large outputs."
                    ),
                )
            if max_results <= 0:
                raise CLIError(
                    "--max-results must be >= 1 when used with --show-list-entry-fields.",
                    exit_code=2,
                    error_type="usage_error",
                )
            if max_results > 3:
                raise CLIError(
                    f"--show-list-entry-fields is limited to --max-results 3 (got {max_results}).",
                    exit_code=2,
                    error_type="usage_error",
                    hint=(
                        "Options: set --max-results 3, use --json for full structured data, or "
                        "use --list-entry-field <field> to project specific fields."
                    ),
                )

        if effective_list_entry_fields and not list_selector:
            for spec in effective_list_entry_fields:
                if any(ch.isspace() for ch in spec):
                    raise CLIError(
                        (
                            "Field names are only allowed with --list because names aren't "
                            "unique across lists."
                        ),
                        exit_code=2,
                        error_type="usage_error",
                        hint=(
                            "Tip: run `affinity list view <list>` to discover list-entry field IDs."
                        ),
                        details={"field": spec},
                    )

        requested_types: list[str] = []
        if all_fields:
            requested_types.extend(list(_COMPANY_FIELDS_ALL_TYPES))
        requested_types.extend([t for t in field_types if t])

        seen_types: set[str] = set()
        deduped_types: list[str] = []
        for t in requested_types:
            if t in seen_types:
                continue
            deduped_types.append(t)
            seen_types.add(t)
        requested_types = deduped_types

        params: dict[str, Any] = {}
        selection_resolved: dict[str, Any] = {}
        if not no_fields and (fields or requested_types):
            if fields:
                selected_field_ids, selection_resolved = _resolve_company_field_ids(
                    client=client,
                    fields=fields,
                    field_types=requested_types,
                )
                if selected_field_ids:
                    params["fieldIds"] = selected_field_ids
            else:
                params["fieldTypes"] = requested_types
                selection_resolved = {"fieldTypes": requested_types}

        company_payload = client._http.get(f"/companies/{int(company_id)}", params=params or None)

        data: dict[str, Any] = {"company": company_payload}
        pagination: dict[str, Any] = {}

        def fetch_v2_collection(
            *,
            path: str,
            section: str,
            default_limit: int,
            default_cap: int | None,
            allow_unbounded: bool,
            keep_item: Callable[[Any], bool] | None = None,
        ) -> list[Any]:
            effective_cap = max_results
            if effective_cap is None and default_cap is not None and not all_pages:
                effective_cap = default_cap
            if effective_cap is not None and effective_cap <= 0:
                return []

            should_paginate = all_pages or allow_unbounded or effective_cap is not None
            limit = default_limit
            if effective_cap is not None:
                limit = min(default_limit, effective_cap)

            truncated_mid_page = False
            payload = client._http.get(path, params={"limit": limit} if limit else None)
            rows = payload.get("data", [])
            if not isinstance(rows, list):
                rows = []
            page_items = list(rows)
            if keep_item is not None:
                page_items = [r for r in page_items if keep_item(r)]
            items: list[Any] = page_items

            page_pagination = payload.get("pagination", {})
            if not isinstance(page_pagination, dict):
                page_pagination = {}
            next_url = page_pagination.get("nextUrl")
            prev_url = page_pagination.get("prevUrl")

            if effective_cap is not None and len(items) > effective_cap:
                truncated_mid_page = True
                items = items[:effective_cap]
                next_url = None

            while (
                should_paginate
                and isinstance(next_url, str)
                and next_url
                and (effective_cap is None or len(items) < effective_cap)
            ):
                payload = client._http.get_url(next_url)
                rows = payload.get("data", [])
                if isinstance(rows, list):
                    page_items = list(rows)
                    if keep_item is not None:
                        page_items = [r for r in page_items if keep_item(r)]
                    items.extend(page_items)
                page_pagination = payload.get("pagination", {})
                if not isinstance(page_pagination, dict):
                    page_pagination = {}
                next_url = page_pagination.get("nextUrl")
                prev_url = page_pagination.get("prevUrl")

                if effective_cap is not None and len(items) > effective_cap:
                    truncated_mid_page = True
                    items = items[:effective_cap]
                    next_url = None
                    break

            if truncated_mid_page and effective_cap is not None:
                warnings.append(
                    f"{section} truncated at {effective_cap:,} items; resume cursor omitted "
                    "to avoid skipping items. Re-run with a higher --max-results "
                    "or with --all."
                )
            elif isinstance(next_url, str) and next_url:
                pagination[section] = {"nextCursor": next_url, "prevCursor": prev_url}

            return items

        if "lists" in expand_set:
            data["lists"] = fetch_v2_collection(
                path=f"/companies/{int(company_id)}/lists",
                section="lists",
                default_limit=100,
                default_cap=100,
                allow_unbounded=True,
            )
        if "list-entries" in expand_set:
            list_id: ListId | None = None
            if list_selector:
                raw_list_selector = list_selector.strip()
                if raw_list_selector.isdigit():
                    list_id = ListId(int(raw_list_selector))
                    resolved.update({"list": {"input": list_selector, "listId": int(list_id)}})
                else:
                    resolved_list_obj = resolve_list_selector(client=client, selector=list_selector)
                    list_id = ListId(int(resolved_list_obj.list.id))
                    resolved.update(resolved_list_obj.resolved)

            def keep_entry(item: Any) -> bool:
                if list_id is None:
                    return True
                return isinstance(item, dict) and item.get("listId") == int(list_id)

            entries_items = fetch_v2_collection(
                path=f"/companies/{int(company_id)}/list-entries",
                section="listEntries",
                default_limit=100,
                default_cap=None,
                allow_unbounded=False,
                keep_item=keep_entry if list_id is not None else None,
            )
            data["listEntries"] = entries_items

            if ctx.output != "json":
                list_name_by_id: dict[int, str] = {}
                if isinstance(data.get("lists"), list):
                    for item in data.get("lists", []):
                        if not isinstance(item, dict):
                            continue
                        lid = item.get("id")
                        name = item.get("name")
                        if isinstance(lid, int) and isinstance(name, str) and name.strip():
                            list_name_by_id[lid] = name.strip()
                if effective_show_list_entry_fields:
                    needed_list_ids: set[int] = set()
                    for entry in entries_items:
                        if not isinstance(entry, dict):
                            continue
                        lid = entry.get("listId")
                        if isinstance(lid, int) and lid not in list_name_by_id:
                            needed_list_ids.add(lid)
                    for lid in sorted(needed_list_ids):
                        try:
                            list_obj = client.lists.get(ListId(lid))
                        except Exception:
                            continue
                        if getattr(list_obj, "name", None):
                            list_name_by_id[lid] = str(list_obj.name)

                resolved_list_entry_fields: list[tuple[str, str]] = []
                if effective_list_entry_fields:
                    if list_id is not None:
                        fields_meta = client.lists.get_fields(list_id)
                        by_id: dict[str, str] = {}
                        by_name: dict[str, list[str]] = {}
                        for f in fields_meta:
                            fid = str(getattr(f, "id", "")).strip()
                            name = str(getattr(f, "name", "")).strip()
                            if fid:
                                by_id[fid] = name or fid
                            if name:
                                by_name.setdefault(name.lower(), []).append(fid or name)

                        for spec in effective_list_entry_fields:
                            raw = spec.strip()
                            if not raw:
                                continue
                            if raw in by_id:
                                resolved_list_entry_fields.append((raw, by_id[raw]))
                                continue
                            matches = by_name.get(raw.lower(), [])
                            if len(matches) == 1:
                                fid = matches[0]
                                resolved_list_entry_fields.append((fid, by_id.get(fid, raw)))
                                continue
                            if len(matches) > 1:
                                raise CLIError(
                                    (
                                        f'Ambiguous list-entry field name "{raw}" '
                                        f"({len(matches)} matches)"
                                    ),
                                    exit_code=2,
                                    error_type="ambiguous_resolution",
                                    details={"name": raw, "matches": matches[:20]},
                                )
                            raise CLIError(
                                f'Unknown list-entry field: "{raw}"',
                                exit_code=2,
                                error_type="usage_error",
                                hint=(
                                    "Tip: run `affinity list view <list>` and inspect "
                                    "`data.fields[*].id` / `data.fields[*].name`."
                                ),
                                details={"field": raw},
                            )
                    else:
                        for spec in effective_list_entry_fields:
                            raw = spec.strip()
                            if raw:
                                resolved_list_entry_fields.append((raw, raw))

                def unique_label(label: str, *, used: set[str], fallback: str) -> str:
                    base = (label or "").strip() or fallback
                    if base not in used:
                        used.add(base)
                        return base
                    idx = 2
                    while f"{base} ({idx})" in used:
                        idx += 1
                    final = f"{base} ({idx})"
                    used.add(final)
                    return final

                used_labels: set[str] = {
                    "list",
                    "listId",
                    "listEntryId",
                    "createdAt",
                    "fieldsCount",
                }
                projected: list[tuple[str, str]] = []
                for fid, label in resolved_list_entry_fields:
                    projected.append((fid, unique_label(label, used=used_labels, fallback=fid)))

                summary_rows: list[dict[str, Any]] = []
                for entry in entries_items:
                    if not isinstance(entry, dict):
                        continue
                    list_id_value = entry.get("listId")
                    list_name = (
                        list_name_by_id.get(list_id_value)
                        if isinstance(list_id_value, int)
                        else None
                    )
                    list_label = list_name or (
                        str(list_id_value) if list_id_value is not None else ""
                    )
                    fields_payload = entry.get("fields", [])
                    fields_list = fields_payload if isinstance(fields_payload, list) else []
                    row: dict[str, Any] = {}
                    row["list"] = list_label
                    row["listId"] = list_id_value if isinstance(list_id_value, int) else None
                    row["listEntryId"] = entry.get("id")
                    row["createdAt"] = entry.get("createdAt")
                    fields_count = len(fields_list)
                    if effective_show_list_entry_fields:
                        _filtered, list_only_count, total_count = filter_list_entry_fields(
                            fields_list,
                            scope=effective_list_entry_fields_scope,
                        )
                        if effective_list_entry_fields_scope == "list-only":
                            fields_count = list_only_count
                        else:
                            fields_count = total_count
                    row["fieldsCount"] = fields_count

                    field_by_id: dict[str, dict[str, Any]] = {}
                    for f in fields_list:
                        if not isinstance(f, dict):
                            continue
                        field_id = f.get("id")
                        if isinstance(field_id, str) and field_id:
                            field_by_id[field_id] = f

                    for fid, label in projected:
                        field_obj = field_by_id.get(fid)
                        value_obj = field_obj.get("value") if isinstance(field_obj, dict) else None
                        row[label] = value_obj

                    summary_rows.append(row)

                data["listEntries"] = summary_rows

                if effective_show_list_entry_fields:
                    for entry in entries_items:
                        if not isinstance(entry, dict):
                            continue
                        list_entry_id = entry.get("id")
                        list_id_value = entry.get("listId")
                        list_name = (
                            list_name_by_id.get(list_id_value)
                            if isinstance(list_id_value, int)
                            else None
                        )
                        if list_name:
                            list_hint = (
                                f"{list_name} (listId={list_id_value})"
                                if list_id_value is not None
                                else str(list_name)
                            )
                        else:
                            list_hint = (
                                f"listId={list_id_value}"
                                if list_id_value is not None
                                else "listId=unknown"
                            )
                        title = f"List Entry {list_entry_id} ({list_hint}) Fields"

                        fields_payload = entry.get("fields", [])
                        fields_list = fields_payload if isinstance(fields_payload, list) else []
                        filtered_fields, list_only_count, total_count = filter_list_entry_fields(
                            fields_list,
                            scope=effective_list_entry_fields_scope,
                        )
                        if total_count == 0:
                            data[title] = {"_text": "(no fields)"}
                            continue
                        if (
                            effective_list_entry_fields_scope == "list-only"
                            and list_only_count == 0
                        ):
                            data[title] = {
                                "_text": (
                                    f"(no list-specific fields; {total_count} non-list fields "
                                    "available with --list-entry-fields-scope all)"
                                )
                            }
                            continue

                        field_rows = build_list_entry_field_rows(filtered_fields)
                        if (
                            effective_list_entry_fields_scope == "list-only"
                            and list_only_count < total_count
                        ):
                            data[title] = {
                                "_rows": field_rows,
                                "_hint": (
                                    "Some non-list fields hidden — use "
                                    "--list-entry-fields-scope all to include them"
                                ),
                            }
                        else:
                            data[title] = field_rows

        if "people" in expand_set:
            people_cap = max_results
            if people_cap is None and not all_pages:
                people_cap = 100
            if people_cap is not None and people_cap <= 0:
                data["people"] = []
            else:
                person_ids = client.companies.get_associated_person_ids(company_id)
                total_people = len(person_ids)
                if people_cap is not None and total_people > people_cap:
                    warnings.append(
                        f"People truncated at {people_cap:,} items; re-run with --all "
                        "or a higher --max-results to fetch more."
                    )

                people = client.companies.get_associated_people(
                    company_id,
                    max_results=people_cap,
                )
                data["people"] = [
                    {
                        "id": int(person.id),
                        "name": person.full_name,
                        "primaryEmail": person.primary_email,
                        "type": (
                            person.type.value
                            if hasattr(person.type, "value")
                            else person.type
                            if person.type
                            else None
                        ),
                    }
                    for person in people
                ]

        if selection_resolved:
            resolved["fieldSelection"] = selection_resolved
        if expand_set:
            resolved["expand"] = sorted(expand_set)

        return CommandOutput(
            data=data,
            pagination=pagination or None,
            resolved=resolved,
            api_called=True,
        )

    run_command(ctx, command="company get", fn=fn)


@company_group.command(name="create", cls=RichCommand)
@click.option("--name", required=True, help="Company name.")
@click.option("--domain", default=None, help="Primary domain.")
@click.option(
    "--person-id",
    "person_ids",
    multiple=True,
    type=int,
    help="Associated person id (repeatable).",
)
@output_options
@click.pass_obj
def company_create(
    ctx: CLIContext,
    *,
    name: str,
    domain: str | None,
    person_ids: tuple[int, ...],
) -> None:
    """Create a company (V1 write path)."""

    def fn(ctx: CLIContext, warnings: list[str]) -> CommandOutput:
        client = ctx.get_client(warnings=warnings)
        created = client.companies.create(
            CompanyCreate(
                name=name,
                domain=domain,
                person_ids=[PersonId(pid) for pid in person_ids],
            )
        )
        payload = created.model_dump(by_alias=True, exclude_none=True)
        return CommandOutput(data={"company": payload}, api_called=True)

    run_command(ctx, command="company create", fn=fn)


@company_group.command(name="update", cls=RichCommand)
@click.argument("company_id", type=int)
@click.option("--name", default=None, help="Updated company name.")
@click.option("--domain", default=None, help="Updated primary domain.")
@click.option(
    "--person-id",
    "person_ids",
    multiple=True,
    type=int,
    help="Replace associated person ids (repeatable).",
)
@output_options
@click.pass_obj
def company_update(
    ctx: CLIContext,
    company_id: int,
    *,
    name: str | None,
    domain: str | None,
    person_ids: tuple[int, ...],
) -> None:
    """Update a company (V1 write path)."""

    def fn(ctx: CLIContext, warnings: list[str]) -> CommandOutput:
        if not (name or domain or person_ids):
            raise CLIError(
                "Provide at least one field to update.",
                exit_code=2,
                error_type="usage_error",
                hint="Use --name, --domain, or --person-id.",
            )
        client = ctx.get_client(warnings=warnings)
        updated = client.companies.update(
            CompanyId(company_id),
            CompanyUpdate(
                name=name,
                domain=domain,
                person_ids=[PersonId(pid) for pid in person_ids] if person_ids else None,
            ),
        )
        payload = updated.model_dump(by_alias=True, exclude_none=True)
        return CommandOutput(data={"company": payload}, api_called=True)

    run_command(ctx, command="company update", fn=fn)


@company_group.command(name="delete", cls=RichCommand)
@click.argument("company_id", type=int)
@output_options
@click.pass_obj
def company_delete(ctx: CLIContext, company_id: int) -> None:
    """Delete a company (V1 write path)."""

    def fn(ctx: CLIContext, warnings: list[str]) -> CommandOutput:
        client = ctx.get_client(warnings=warnings)
        success = client.companies.delete(CompanyId(company_id))
        return CommandOutput(data={"success": success}, api_called=True)

    run_command(ctx, command="company delete", fn=fn)


@company_group.command(name="merge", cls=RichCommand)
@click.argument("primary_id", type=int)
@click.argument("duplicate_id", type=int)
@output_options
@click.pass_obj
def company_merge(
    ctx: CLIContext,
    primary_id: int,
    duplicate_id: int,
) -> None:
    """Merge a duplicate company into a primary company (beta)."""

    def fn(ctx: CLIContext, warnings: list[str]) -> CommandOutput:
        client = ctx.get_client(warnings=warnings)
        task_url = client.companies.merge(
            CompanyId(primary_id),
            CompanyId(duplicate_id),
        )
        return CommandOutput(data={"taskUrl": task_url}, api_called=True)

    run_command(ctx, command="company merge", fn=fn)
