from __future__ import annotations

import asyncio

from affinity.models.entities import Company
from affinity.types import CompanyId

from ..click_compat import RichCommand, RichGroup, click
from ..context import CLIContext
from ..options import output_options
from ..runner import CommandOutput, run_command
from ._entity_files_dump import dump_entity_files_bundle


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
    def fn(ctx: CLIContext, warnings: list[str]) -> CommandOutput:
        client = ctx.get_client(warnings=warnings)
        results: list[dict[str, object]] = []
        next_token = page_token

        fetched_first_page = False
        while True:
            resp = client.companies.search(
                query,
                with_interaction_dates=True,
                page_size=page_size,
                page_token=next_token,
            )
            fetched_first_page = True
            for company in resp.data:
                results.append(_company_row(company))
                if max_results is not None and len(results) >= max_results:
                    return CommandOutput(
                        data=results[:max_results],
                        pagination={"nextPageToken": resp.next_page_token},
                        api_called=True,
                    )

            if not resp.next_page_token:
                return CommandOutput(data=results, pagination=None, api_called=True)

            if not all_pages and fetched_first_page and max_results is None:
                return CommandOutput(
                    data=results,
                    pagination={"nextPageToken": resp.next_page_token},
                    api_called=True,
                )

            next_token = resp.next_page_token

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
