from __future__ import annotations

from typing import Any

from affinity.models.entities import Opportunity, OpportunityCreate, OpportunityUpdate
from affinity.models.pagination import PaginationInfo
from affinity.models.types import ListType
from affinity.types import CompanyId, ListId, OpportunityId, PersonId

from ..click_compat import RichCommand, RichGroup, click
from ..context import CLIContext
from ..errors import CLIError
from ..options import output_options
from ..resolve import resolve_list_selector
from ..runner import CommandOutput, run_command
from .resolve_url_cmd import _parse_affinity_url


@click.group(name="opportunity", cls=RichGroup)
def opportunity_group() -> None:
    """Opportunity commands."""


def _opportunity_row(item: dict[str, Any]) -> dict[str, object]:
    raw_id = item.get("id")
    raw_list_id = item.get("listId")
    ident = raw_id
    if (isinstance(raw_id, (int, float)) and not isinstance(raw_id, bool)) or (
        isinstance(raw_id, str) and raw_id.isdigit()
    ):
        ident = int(raw_id)
    list_id = raw_list_id
    if (isinstance(raw_list_id, (int, float)) and not isinstance(raw_list_id, bool)) or (
        isinstance(raw_list_id, str) and raw_list_id.isdigit()
    ):
        list_id = int(raw_list_id)
    return {
        "id": ident,
        "name": item.get("name"),
        "listId": list_id,
    }


def _resolve_opportunity_selector(
    *,
    selector: str,
) -> tuple[OpportunityId, dict[str, Any]]:
    raw = selector.strip()
    if raw.isdigit():
        opportunity_id = OpportunityId(int(raw))
        return opportunity_id, {
            "opportunity": {
                "input": selector,
                "opportunityId": int(opportunity_id),
                "source": "id",
            }
        }

    if raw.startswith(("http://", "https://")):
        resolved = _parse_affinity_url(raw)
        if resolved.type != "opportunity" or resolved.opportunity_id is None:
            raise CLIError(
                "Expected an opportunity URL like https://<tenant>.affinity.(co|com)/opportunities/<id>",
                exit_code=2,
                error_type="usage_error",
                details={"input": selector, "resolvedType": resolved.type},
            )
        opportunity_id = OpportunityId(int(resolved.opportunity_id))
        return opportunity_id, {
            "opportunity": {
                "input": selector,
                "opportunityId": int(opportunity_id),
                "source": "url",
                "canonicalUrl": f"https://app.affinity.co/opportunities/{int(opportunity_id)}",
            }
        }

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
@output_options
@click.pass_obj
def opportunity_ls(
    ctx: CLIContext,
    *,
    page_size: int | None,
    cursor: str | None,
    max_results: int | None,
    all_pages: bool,
) -> None:
    """
    List opportunities (basic v2 representation).

    Examples:
    - `affinity opportunity ls`
    - `affinity opportunity ls --page-size 200`
    - `affinity opportunity ls --cursor <cursor>`
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
        next_url = cursor
        while True:
            if next_url:
                payload = client._http.get_url(next_url)
            else:
                params = {"limit": page_size} if page_size else None
                payload = client._http.get("/opportunities", params=params)

            items = payload.get("data", [])
            if not isinstance(items, list):
                items = []
            for idx, item in enumerate(items):
                if isinstance(item, dict):
                    rows.append(_opportunity_row(item))
                if max_results is not None and len(rows) >= max_results:
                    stopped_mid_page = idx < (len(items) - 1)
                    if stopped_mid_page:
                        warnings.append(
                            "Results truncated mid-page; resume cursor omitted "
                            "to avoid skipping items. Re-run with a higher "
                            "--max-results or without it to paginate safely."
                        )
                    pagination = None
                    if not stopped_mid_page:
                        page_pagination = payload.get("pagination", {})
                        if isinstance(page_pagination, dict):
                            page_info = PaginationInfo.model_validate(page_pagination)
                            if page_info.next_cursor:
                                pagination = {
                                    "opportunities": {
                                        "nextCursor": page_info.next_cursor,
                                        "prevCursor": page_info.prev_cursor,
                                    }
                                }
                    return CommandOutput(
                        data={"opportunities": rows[:max_results]},
                        pagination=pagination,
                        api_called=True,
                    )

            page_pagination = payload.get("pagination", {})
            if not isinstance(page_pagination, dict):
                page_pagination = {}
            page_info = PaginationInfo.model_validate(page_pagination)
            next_url = page_info.next_cursor

            if first_page and not all_pages and max_results is None:
                pagination = None
                if page_info.next_cursor:
                    pagination = {
                        "opportunities": {
                            "nextCursor": page_info.next_cursor,
                            "prevCursor": page_info.prev_cursor,
                        }
                    }
                return CommandOutput(
                    data={"opportunities": rows},
                    pagination=pagination,
                    api_called=True,
                )
            first_page = False

            if not next_url:
                break

        return CommandOutput(data={"opportunities": rows}, pagination=None, api_called=True)

    run_command(ctx, command="opportunity ls", fn=fn)


@opportunity_group.command(name="get", cls=RichCommand)
@click.argument("opportunity_selector")
@click.option(
    "--details",
    "details",
    is_flag=True,
    help="Fetch a fuller payload with associations and list entries.",
)
@output_options
@click.pass_obj
def opportunity_get(
    ctx: CLIContext,
    opportunity_selector: str,
    *,
    details: bool,
) -> None:
    """
    Get an opportunity by id or URL.

    Examples:
    - `affinity opportunity get 123`
    - `affinity opportunity get https://mydomain.affinity.com/opportunities/123`
    - `affinity opportunity get 123 --details`
    """

    def fn(ctx: CLIContext, warnings: list[str]) -> CommandOutput:
        client = ctx.get_client(warnings=warnings)
        opportunity_id, resolved = _resolve_opportunity_selector(selector=opportunity_selector)

        payload = client._http.get(
            f"/opportunities/{int(opportunity_id)}",
            v1=details,
        )

        data: dict[str, Any]
        if isinstance(payload, dict):
            opp = Opportunity.model_validate(payload)
            data = opp.model_dump(by_alias=True, exclude_none=True)
            if "fields" not in payload:
                data.pop("fields", None)
        else:
            data = {"value": payload}

        return CommandOutput(
            data={"opportunity": data},
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
    - `affinity opportunity create --name "Series A" --list "Dealflow"`
    - `affinity opportunity create --name "Series A" --list 123 --person-id 1 --company-id 2`
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
            organization_ids=[CompanyId(cid) for cid in company_ids],
        )
        created = client.opportunities.create(data)
        payload = created.model_dump(by_alias=True, exclude_none=True)

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
    - `affinity opportunity update 123 --name "Series A (Closed)"`
    - `affinity opportunity update 123 --person-id 1 --person-id 2`
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
            organization_ids=[CompanyId(cid) for cid in company_ids] if company_ids else None,
        )
        updated = client.opportunities.update(OpportunityId(opportunity_id), data)
        payload = updated.model_dump(by_alias=True, exclude_none=True)

        return CommandOutput(
            data={"opportunity": payload},
            resolved={"opportunity": {"opportunityId": int(opportunity_id), "source": "id"}},
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
    - `affinity opportunity delete 123`
    """

    def fn(ctx: CLIContext, warnings: list[str]) -> CommandOutput:
        client = ctx.get_client(warnings=warnings)
        success = client.opportunities.delete(OpportunityId(opportunity_id))
        return CommandOutput(
            data={"opportunityId": opportunity_id, "success": success},
            resolved={"opportunity": {"opportunityId": int(opportunity_id), "source": "id"}},
            api_called=True,
        )

    run_command(ctx, command="opportunity delete", fn=fn)
