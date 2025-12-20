from __future__ import annotations

import asyncio

from affinity.models.entities import Person
from affinity.types import PersonId

from ..click_compat import RichCommand, RichGroup, click
from ..context import CLIContext
from ..options import output_options
from ..runner import CommandOutput, run_command
from ._entity_files_dump import dump_entity_files_bundle


@click.group(name="person", cls=RichGroup)
def person_group() -> None:
    """Person commands."""


@person_group.command(name="search", cls=RichCommand)
@click.argument("query")
@click.option("--page-size", type=int, default=None, help="v1 page size (max 500).")
@click.option("--page-token", type=str, default=None, help="v1 page token for resuming.")
@click.option("--max-results", type=int, default=None, help="Stop after N results total.")
@click.option("--all", "all_pages", is_flag=True, help="Fetch all pages.")
@output_options
@click.pass_obj
def person_search(
    ctx: CLIContext,
    query: str,
    *,
    page_size: int | None,
    page_token: str | None,
    max_results: int | None,
    all_pages: bool,
) -> None:
    """
    Search people by name or email.

    `QUERY` is a free-text term passed to Affinity's person search. Typical inputs:

    - Email: `alice@example.com`
    - Name: `Alice` (or `Alice Smith`)

    Examples:

    - `affinity person search alice@example.com`
    - `affinity person search \"Alice\" --all`
    """

    def fn(ctx: CLIContext, warnings: list[str]) -> CommandOutput:
        client = ctx.get_client(warnings=warnings)
        results: list[dict[str, object]] = []
        first_page = True
        for page in client.persons.search_pages(
            query,
            with_interaction_dates=True,
            page_size=page_size,
            page_token=page_token,
        ):
            for person in page.data:
                results.append(_person_row(person))
                if max_results is not None and len(results) >= max_results:
                    return CommandOutput(
                        data={"persons": results[:max_results]},
                        pagination={
                            "persons": {
                                "nextPageToken": page.next_page_token,
                                "prevPageToken": None,
                            }
                        }
                        if page.next_page_token
                        else None,
                        api_called=True,
                    )

            if first_page and not all_pages and max_results is None:
                return CommandOutput(
                    data={"persons": results},
                    pagination={
                        "persons": {"nextPageToken": page.next_page_token, "prevPageToken": None}
                    }
                    if page.next_page_token
                    else None,
                    api_called=True,
                )
            first_page = False

        return CommandOutput(data={"persons": results}, pagination=None, api_called=True)

    run_command(ctx, command="person search", fn=fn)


def _person_row(person: Person) -> dict[str, object]:
    last_interaction = None
    if person.interaction_dates is not None:
        last_interaction = person.interaction_dates.last_interaction_date
    return {
        "id": int(person.id),
        "name": person.full_name,
        "primaryEmail": person.primary_email,
        "emails": person.emails,
        "lastInteractionDate": last_interaction,
    }


@person_group.group(name="files", cls=RichGroup)
def person_files_group() -> None:
    """Person files."""


@person_files_group.command(name="dump", cls=RichCommand)
@click.argument("person_id", type=int)
@click.option("--out", "out_dir", type=click.Path(), default=None)
@click.option("--overwrite", is_flag=True, help="Overwrite existing files.")
@click.option("--concurrency", type=int, default=3, show_default=True)
@click.option("--page-size", type=int, default=200, show_default=True)
@click.option("--max-files", type=int, default=None, help="Stop after N files.")
@output_options
@click.pass_obj
def person_files_dump(
    ctx: CLIContext,
    person_id: int,
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
                default_dirname=f"affinity-person-{person_id}-files",
                manifest_entity={"type": "person", "personId": person_id},
                files_list_kwargs={"person_id": PersonId(person_id)},
            )
        )

    run_command(ctx, command="person files dump", fn=fn)
