from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from affinity.models.entities import Company
from affinity.types import CompanyId, FieldType, ListId

from ..click_compat import RichCommand, RichGroup, click
from ..context import CLIContext
from ..errors import CLIError
from ..options import output_options
from ..resolve import resolve_list_selector
from ..runner import CommandOutput, run_command
from ._entity_files_dump import dump_entity_files_bundle
from .resolve_url_cmd import _parse_affinity_url


@click.group(name="company", cls=RichGroup)
def company_group() -> None:
    """Company commands."""


@company_group.command(name="search", cls=RichCommand)
@click.argument("query")
@click.option("--page-size", type=int, default=None, help="v1 page size (max 500).")
@click.option("--page-token", type=str, default=None, help="v1 page token for resuming.")
@click.option("--max-results", type=int, default=None, help="Stop after N results total.")
@click.option("--all", "all_pages", is_flag=True, help="Fetch all pages.")
@output_options
@click.pass_obj
def company_search(
    ctx: CLIContext,
    query: str,
    *,
    page_size: int | None,
    page_token: str | None,
    max_results: int | None,
    all_pages: bool,
) -> None:
    """
    Search companies by name or domain.

    `QUERY` is a free-text term passed to Affinity's company search. Typical inputs:

    - Domain: `longevitix.co`
    - Company name: `Longevitix`

    Examples:

    - `affinity company search longevitix`
    - `affinity company search longevitix.co`
    """

    def fn(ctx: CLIContext, warnings: list[str]) -> CommandOutput:
        client = ctx.get_client(warnings=warnings)
        results: list[dict[str, object]] = []
        first_page = True
        for page in client.companies.search_pages(
            query,
            with_interaction_dates=True,
            page_size=page_size,
            page_token=page_token,
        ):
            for idx, company in enumerate(page.data):
                results.append(_company_row(company))
                if max_results is not None and len(results) >= max_results:
                    stopped_mid_page = idx < (len(page.data) - 1)
                    if stopped_mid_page:
                        warnings.append(
                            "Results truncated mid-page; resume token omitted "
                            "to avoid skipping items. Re-run with a higher "
                            "--max-results or without it to paginate safely."
                        )
                    return CommandOutput(
                        data={"companies": results[:max_results]},
                        pagination={
                            "companies": {
                                "nextPageToken": page.next_page_token,
                                "prevPageToken": None,
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
                        "companies": {"nextPageToken": page.next_page_token, "prevPageToken": None}
                    }
                    if page.next_page_token
                    else None,
                    api_called=True,
                )
            first_page = False

        return CommandOutput(data={"companies": results}, pagination=None, api_called=True)

    run_command(ctx, command="company search", fn=fn)


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
                files_list_kwargs={"organization_id": CompanyId(company_id)},
            )
        )

    run_command(ctx, command="company files dump", fn=fn)


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
    type=click.Choice(["lists", "list-entries"]),
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
                    f"{section} truncated at {effective_cap:,} items; resume URL omitted "
                    "to avoid skipping items. Re-run with a higher --max-results "
                    "or with --all."
                )
            elif isinstance(next_url, str) and next_url:
                pagination[section] = {"nextUrl": next_url, "prevUrl": prev_url}

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
