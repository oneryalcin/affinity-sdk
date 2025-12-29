from __future__ import annotations

from pathlib import Path
from typing import Any

from affinity.models.entities import Opportunity, OpportunityCreate, OpportunityUpdate
from affinity.models.types import ListType
from affinity.types import CompanyId, ListId, OpportunityId, PersonId

from ..click_compat import RichCommand, RichGroup, click
from ..context import CLIContext
from ..csv_utils import artifact_path, write_csv_from_rows
from ..errors import CLIError
from ..options import output_options
from ..progress import ProgressManager, ProgressSettings
from ..resolve import resolve_list_selector
from ..resolvers import ResolvedEntity
from ..results import Artifact
from ..runner import CommandOutput, run_command
from ..serialization import serialize_model_for_cli
from .resolve_url_cmd import _parse_affinity_url


@click.group(name="opportunity", cls=RichGroup)
def opportunity_group() -> None:
    """Opportunity commands."""


def _resolve_opportunity_selector(
    *,
    selector: str,
) -> tuple[OpportunityId, dict[str, Any]]:
    raw = selector.strip()
    if raw.isdigit():
        opportunity_id = OpportunityId(int(raw))
        resolved = ResolvedEntity(
            input=selector,
            entity_id=int(opportunity_id),
            entity_type="opportunity",
            source="id",
        )
        return opportunity_id, {"opportunity": resolved.to_dict()}

    if raw.startswith(("http://", "https://")):
        url_parsed = _parse_affinity_url(raw)
        if url_parsed.type != "opportunity" or url_parsed.opportunity_id is None:
            raise CLIError(
                "Expected an opportunity URL like https://<tenant>.affinity.(co|com)/opportunities/<id>",
                exit_code=2,
                error_type="usage_error",
                details={"input": selector, "resolvedType": url_parsed.type},
            )
        opportunity_id = OpportunityId(int(url_parsed.opportunity_id))
        url_resolved = ResolvedEntity(
            input=selector,
            entity_id=int(opportunity_id),
            entity_type="opportunity",
            source="url",
            canonical_url=f"https://app.affinity.co/opportunities/{int(opportunity_id)}",
        )
        return opportunity_id, {"opportunity": url_resolved.to_dict()}

    raise CLIError(
        "Unrecognized opportunity selector.",
        exit_code=2,
        error_type="usage_error",
        hint='Use a numeric id or an Affinity URL like "https://<tenant>.affinity.co/opportunities/<id>".',
        details={"input": selector},
    )


@opportunity_group.command(name="ls", cls=RichCommand)
@click.option("--page-size", type=int, default=None, help="Page size (limit).")
@click.option("--cursor", type=str, default=None, help="Resume from a prior cursor.")
@click.option("--max-results", type=int, default=None, help="Stop after N items total.")
@click.option("--all", "all_pages", is_flag=True, help="Fetch all pages.")
@click.option("--csv", "csv_path", type=click.Path(), default=None, help="Write CSV output.")
@click.option("--csv-bom", is_flag=True, help="Write UTF-8 BOM for Excel compatibility.")
@output_options
@click.pass_obj
def opportunity_ls(
    ctx: CLIContext,
    *,
    page_size: int | None,
    cursor: str | None,
    max_results: int | None,
    all_pages: bool,
    csv_path: str | None,
    csv_bom: bool,
) -> None:
    """
    List opportunities (basic v2 representation).

    Examples:
    - `xaffinityopportunity ls`
    - `xaffinityopportunity ls --page-size 200`
    - `xaffinityopportunity ls --cursor <cursor>`
    - `xaffinityopportunity ls --all --csv opportunities.csv`
    - `xaffinityopportunity ls --all --csv opportunities.csv --csv-bom`
    """

    def fn(ctx: CLIContext, warnings: list[str]) -> CommandOutput:
        client = ctx.get_client(warnings=warnings)

        if cursor is not None and page_size is not None:
            raise CLIError(
                "--cursor cannot be combined with --page-size.",
                exit_code=2,
                error_type="usage_error",
            )

        rows: list[dict[str, object]] = []
        first_page = True

        pages_iter = client.opportunities.pages(limit=page_size, cursor=cursor)

        for page in pages_iter:
            for idx, opportunity in enumerate(page.data):
                rows.append(_opportunity_ls_row(opportunity))
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
                            "opportunities": {
                                "nextCursor": page.pagination.next_cursor,
                                "prevCursor": page.pagination.prev_cursor,
                            }
                        }
                    return CommandOutput(
                        data={"opportunities": rows[:max_results]},
                        pagination=pagination,
                        api_called=True,
                    )

            if first_page and not all_pages and max_results is None:
                return CommandOutput(
                    data={"opportunities": rows},
                    pagination=(
                        {
                            "opportunities": {
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

        # CSV export path
        if csv_path:
            csv_path_obj = Path(csv_path)
            write_result = write_csv_from_rows(
                path=csv_path_obj,
                rows=rows,
                bom=csv_bom,
            )

            csv_ref, csv_is_relative = artifact_path(csv_path_obj)
            return CommandOutput(
                data={
                    "csv": csv_ref,
                    "rowsWritten": write_result.rows_written,
                },
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
                api_called=True,
            )

        return CommandOutput(data={"opportunities": rows}, pagination=None, api_called=True)

    run_command(ctx, command="opportunity ls", fn=fn)


def _opportunity_ls_row(opportunity: Opportunity) -> dict[str, object]:
    """Build a row for opportunity ls output."""
    return {
        "id": int(opportunity.id),
        "name": opportunity.name,
        "listId": int(opportunity.list_id) if opportunity.list_id else None,
    }


@opportunity_group.command(name="get", cls=RichCommand)
@click.argument("opportunity_selector")
@click.option(
    "--details",
    "details",
    is_flag=True,
    help="Fetch a fuller payload with associations and list entries.",
)
@click.option(
    "--expand",
    "expand",
    multiple=True,
    type=click.Choice(["people", "companies"]),
    help="Include related data (repeatable). Uses V1 API for associations.",
)
@click.option(
    "--max-results",
    type=int,
    default=None,
    help="Maximum items per expansion (default: 100).",
)
@click.option(
    "--all",
    "all_pages",
    is_flag=True,
    help="Fetch all expanded items (no limit).",
)
@output_options
@click.pass_obj
def opportunity_get(
    ctx: CLIContext,
    opportunity_selector: str,
    *,
    details: bool,
    expand: tuple[str, ...],
    max_results: int | None,
    all_pages: bool,
) -> None:
    """
    Get an opportunity by id or URL.

    Examples:
    - `xaffinityopportunity get 123`
    - `xaffinityopportunity get https://mydomain.affinity.com/opportunities/123`
    - `xaffinityopportunity get 123 --details`
    - `xaffinityopportunity get 123 --expand people`
    - `xaffinityopportunity get 123 --expand people --expand companies`
    """

    def fn(ctx: CLIContext, warnings: list[str]) -> CommandOutput:
        client = ctx.get_client(warnings=warnings)
        opportunity_id, resolved = _resolve_opportunity_selector(selector=opportunity_selector)

        expand_set = {e.strip() for e in expand if e and e.strip()}

        # Use service methods instead of raw HTTP
        if details:
            opp = client.opportunities.get_details(opportunity_id)
        else:
            opp = client.opportunities.get(opportunity_id)

        data: dict[str, Any] = {"opportunity": serialize_model_for_cli(opp)}
        if not details and not opp.fields:
            data["opportunity"].pop("fields", None)

        # Fetch associations once if both people and companies are requested (saves 1 V1 call)
        want_people = "people" in expand_set
        want_companies = "companies" in expand_set
        cached_person_ids: list[int] | None = None
        cached_company_ids: list[int] | None = None

        if want_people and want_companies:
            assoc = client.opportunities.get_associations(opportunity_id)
            cached_person_ids = [int(pid) for pid in assoc.person_ids]
            cached_company_ids = [int(cid) for cid in assoc.company_ids]

        # Handle people expansion
        if want_people:
            people_cap = max_results
            if people_cap is None and not all_pages:
                people_cap = 100
            if people_cap is not None and people_cap <= 0:
                data["people"] = []
            else:
                # Use cached IDs if available, otherwise fetch
                if cached_person_ids is not None:
                    person_ids = cached_person_ids
                else:
                    person_ids = [
                        int(pid)
                        for pid in client.opportunities.get_associated_person_ids(opportunity_id)
                    ]
                total_people = len(person_ids)
                if people_cap is not None and total_people > people_cap:
                    warnings.append(
                        f"People truncated at {people_cap:,} items; re-run with --all "
                        "or a higher --max-results to fetch more."
                    )
                    if total_people > 50:
                        warnings.append(
                            f"Fetching {min(people_cap, total_people)} people requires "
                            f"{min(people_cap, total_people) + 1} API calls."
                        )

                people = client.opportunities.get_associated_people(
                    opportunity_id,
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

        # Handle companies expansion
        if want_companies:
            companies_cap = max_results
            if companies_cap is None and not all_pages:
                companies_cap = 100
            if companies_cap is not None and companies_cap <= 0:
                data["companies"] = []
            else:
                # Use cached IDs if available, otherwise fetch
                if cached_company_ids is not None:
                    company_ids = cached_company_ids
                else:
                    company_ids = [
                        int(cid)
                        for cid in client.opportunities.get_associated_company_ids(opportunity_id)
                    ]
                total_companies = len(company_ids)
                if companies_cap is not None and total_companies > companies_cap:
                    warnings.append(
                        f"Companies truncated at {companies_cap:,} items; re-run with --all "
                        "or a higher --max-results to fetch more."
                    )

                companies = client.opportunities.get_associated_companies(
                    opportunity_id,
                    max_results=companies_cap,
                )
                data["companies"] = [
                    {
                        "id": int(company.id),
                        "name": company.name,
                        "domain": company.domain,
                    }
                    for company in companies
                ]

        if expand_set:
            resolved["expand"] = sorted(expand_set)

        return CommandOutput(
            data=data,
            resolved=resolved,
            api_called=True,
        )

    run_command(ctx, command="opportunity get", fn=fn)


@opportunity_group.command(name="create", cls=RichCommand)
@click.option("--name", required=True, help="Opportunity name.")
@click.option("--list", "list_selector", required=True, help="List id or exact list name.")
@click.option(
    "--person-id",
    "person_ids",
    multiple=True,
    type=int,
    help="Associate a person id (repeatable).",
)
@click.option(
    "--company-id",
    "company_ids",
    multiple=True,
    type=int,
    help="Associate a company id (repeatable).",
)
@output_options
@click.pass_obj
def opportunity_create(
    ctx: CLIContext,
    *,
    name: str,
    list_selector: str,
    person_ids: tuple[int, ...],
    company_ids: tuple[int, ...],
) -> None:
    """
    Create a new opportunity.

    Examples:
    - `xaffinityopportunity create --name "Series A" --list "Dealflow"`
    - `xaffinityopportunity create --name "Series A" --list 123 --person-id 1 --company-id 2`
    """

    def fn(ctx: CLIContext, warnings: list[str]) -> CommandOutput:
        client = ctx.get_client(warnings=warnings)
        resolved_list = resolve_list_selector(client=client, selector=list_selector)
        if resolved_list.list.type != ListType.OPPORTUNITY:
            raise CLIError(
                "List is not an opportunity list.",
                exit_code=2,
                error_type="usage_error",
                details={
                    "listId": int(resolved_list.list.id),
                    "listType": resolved_list.list.type,
                },
            )

        data = OpportunityCreate(
            name=name,
            list_id=ListId(int(resolved_list.list.id)),
            person_ids=[PersonId(pid) for pid in person_ids],
            company_ids=[CompanyId(cid) for cid in company_ids],
        )
        created = client.opportunities.create(data)
        payload = serialize_model_for_cli(created)

        return CommandOutput(
            data={"opportunity": payload},
            resolved=resolved_list.resolved,
            api_called=True,
        )

    run_command(ctx, command="opportunity create", fn=fn)


@opportunity_group.command(name="update", cls=RichCommand)
@click.argument("opportunity_id", type=int)
@click.option("--name", default=None, help="Updated opportunity name.")
@click.option(
    "--person-id",
    "person_ids",
    multiple=True,
    type=int,
    help="Replace associated person ids (repeatable).",
)
@click.option(
    "--company-id",
    "company_ids",
    multiple=True,
    type=int,
    help="Replace associated company ids (repeatable).",
)
@output_options
@click.pass_obj
def opportunity_update(
    ctx: CLIContext,
    opportunity_id: int,
    *,
    name: str | None,
    person_ids: tuple[int, ...],
    company_ids: tuple[int, ...],
) -> None:
    """
    Update an opportunity (replaces association arrays when provided).

    Examples:
    - `xaffinityopportunity update 123 --name "Series A (Closed)"`
    - `xaffinityopportunity update 123 --person-id 1 --person-id 2`
    """

    def fn(ctx: CLIContext, warnings: list[str]) -> CommandOutput:
        client = ctx.get_client(warnings=warnings)

        if name is None and not person_ids and not company_ids:
            raise CLIError(
                "No updates specified.",
                exit_code=2,
                error_type="usage_error",
                hint="Provide at least one of --name, --person-id, or --company-id.",
            )

        data = OpportunityUpdate(
            name=name,
            person_ids=[PersonId(pid) for pid in person_ids] if person_ids else None,
            company_ids=[CompanyId(cid) for cid in company_ids] if company_ids else None,
        )
        updated = client.opportunities.update(OpportunityId(opportunity_id), data)
        payload = serialize_model_for_cli(updated)

        resolved = ResolvedEntity(
            input=str(opportunity_id),
            entity_id=int(opportunity_id),
            entity_type="opportunity",
            source="id",
        )

        return CommandOutput(
            data={"opportunity": payload},
            resolved={"opportunity": resolved.to_dict()},
            api_called=True,
        )

    run_command(ctx, command="opportunity update", fn=fn)


@opportunity_group.command(name="delete", cls=RichCommand)
@click.argument("opportunity_id", type=int)
@output_options
@click.pass_obj
def opportunity_delete(
    ctx: CLIContext,
    opportunity_id: int,
) -> None:
    """
    Delete an opportunity.

    Example:
    - `xaffinityopportunity delete 123`
    """

    def fn(ctx: CLIContext, warnings: list[str]) -> CommandOutput:
        client = ctx.get_client(warnings=warnings)
        success = client.opportunities.delete(OpportunityId(opportunity_id))

        resolved = ResolvedEntity(
            input=str(opportunity_id),
            entity_id=int(opportunity_id),
            entity_type="opportunity",
            source="id",
        )

        return CommandOutput(
            data={"opportunityId": opportunity_id, "success": success},
            resolved={"opportunity": resolved.to_dict()},
            api_called=True,
        )

    run_command(ctx, command="opportunity delete", fn=fn)


@opportunity_group.group(name="files", cls=RichGroup)
def opportunity_files_group() -> None:
    """Opportunity files."""


@opportunity_files_group.command(name="upload", cls=RichCommand)
@click.argument("opportunity_id", type=int)
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
def opportunity_files_upload(
    ctx: CLIContext,
    opportunity_id: int,
    *,
    file_paths: tuple[str, ...],
) -> None:
    """
    Upload files to an opportunity.

    Examples:

    - `xaffinityopportunity files upload 123 --file doc.pdf`
    - `xaffinityopportunity files upload 123 --file a.pdf --file b.pdf`
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
                    opportunity_id=OpportunityId(opportunity_id),
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
            data={"uploads": results, "opportunityId": opportunity_id},
            api_called=True,
        )

    run_command(ctx, command="opportunity files upload", fn=fn)
