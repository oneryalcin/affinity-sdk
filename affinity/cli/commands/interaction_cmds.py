from __future__ import annotations

import sys
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone

from rich.console import Console
from rich.progress import BarColumn, Progress, TaskID, TextColumn, TimeElapsedColumn

from affinity.models.secondary import Interaction, InteractionCreate, InteractionUpdate
from affinity.models.types import InteractionDirection, InteractionType
from affinity.types import CompanyId, InteractionId, OpportunityId, PersonId

from ..click_compat import RichCommand, RichGroup, click
from ..context import CLIContext
from ..decorators import category, destructive
from ..errors import CLIError
from ..options import output_options
from ..results import CommandContext
from ..runner import CommandOutput, run_command
from ._v1_parsing import parse_choice, parse_iso_datetime


@click.group(name="interaction", cls=RichGroup)
def interaction_group() -> None:
    """Interaction commands."""


_INTERACTION_TYPE_MAP = {
    "meeting": InteractionType.MEETING,
    "call": InteractionType.CALL,
    "chat-message": InteractionType.CHAT_MESSAGE,
    "chat": InteractionType.CHAT_MESSAGE,
    "email": InteractionType.EMAIL,
}

_INTERACTION_DIRECTION_MAP = {
    "outgoing": InteractionDirection.OUTGOING,
    "incoming": InteractionDirection.INCOMING,
}


def _interaction_payload(interaction: Interaction) -> dict[str, object]:
    # Convert enum values back to names for CLI display
    type_name = InteractionType(interaction.type).name.lower().replace("_", "-")
    direction_name = (
        InteractionDirection(interaction.direction).name.lower()
        if interaction.direction is not None
        else None
    )
    return {
        "id": int(interaction.id),
        "type": type_name,
        "date": interaction.date,
        "direction": direction_name,
        "title": interaction.title,
        "subject": interaction.subject,
        "startTime": interaction.start_time,
        "endTime": interaction.end_time,
        "personIds": [int(p.id) for p in interaction.persons],
        "attendees": interaction.attendees,
        "notes": [int(n) for n in interaction.notes],
    }


@category("read")
@interaction_group.command(name="ls", cls=RichCommand)
@click.option(
    "--type",
    "-t",
    "interaction_type",
    type=click.Choice(sorted(_INTERACTION_TYPE_MAP.keys())),
    default=None,
    help="Interaction type (meeting, call, chat-message, email).",
)
@click.option("--start-time", type=str, default=None, help="Start time (ISO-8601).")
@click.option("--end-time", type=str, default=None, help="End time (ISO-8601).")
@click.option("--person-id", type=int, default=None, help="Filter by person id.")
@click.option("--company-id", type=int, default=None, help="Filter by company id.")
@click.option("--opportunity-id", type=int, default=None, help="Filter by opportunity id.")
@click.option("--page-size", "-s", type=int, default=None, help="Page size (max 500).")
@click.option(
    "--cursor", type=str, default=None, help="Resume from cursor (incompatible with --page-size)."
)
@click.option("--max-results", "-n", type=int, default=None, help="Stop after N results total.")
@click.option("--all", "-A", "all_pages", is_flag=True, help="Fetch all pages.")
@output_options
@click.pass_obj
def interaction_ls(
    ctx: CLIContext,
    *,
    interaction_type: str | None,
    start_time: str | None,
    end_time: str | None,
    person_id: int | None,
    company_id: int | None,
    opportunity_id: int | None,
    page_size: int | None,
    cursor: str | None,
    max_results: int | None,
    all_pages: bool,
) -> None:
    """List interactions."""

    def fn(ctx: CLIContext, warnings: list[str]) -> CommandOutput:
        nonlocal start_time, end_time

        # Validate that at least one entity ID is provided
        entity_count = sum(1 for x in [person_id, company_id, opportunity_id] if x is not None)
        if entity_count == 0:
            raise CLIError(
                "At least one of --person-id, --company-id, or --opportunity-id is required.",
                error_type="usage_error",
                exit_code=2,
            )
        if entity_count > 1:
            raise CLIError(
                "Only one of --person-id, --company-id, or --opportunity-id can be specified.",
                error_type="usage_error",
                exit_code=2,
            )

        # Apply smart date defaults if no date filters provided
        if not start_time and not end_time:
            now = datetime.now(timezone.utc)
            start_time = (now - timedelta(days=7)).isoformat()
            end_time = now.isoformat()
            if not ctx.quiet:
                click.echo(
                    "Note: Using default date range: last 7 days (API max: 1 year)",
                    err=True,
                )

        client = ctx.get_client(warnings=warnings)
        results: list[dict[str, object]] = []
        first_page = True
        page_token = cursor

        # Build CommandContext upfront for all return paths
        ctx_modifiers: dict[str, object] = {}
        if interaction_type:
            ctx_modifiers["type"] = interaction_type
        if start_time:
            ctx_modifiers["startTime"] = start_time
        if end_time:
            ctx_modifiers["endTime"] = end_time
        if person_id is not None:
            ctx_modifiers["personId"] = person_id
        if company_id is not None:
            ctx_modifiers["companyId"] = company_id
        if opportunity_id is not None:
            ctx_modifiers["opportunityId"] = opportunity_id
        if page_size is not None:
            ctx_modifiers["pageSize"] = page_size
        if cursor is not None:
            ctx_modifiers["cursor"] = cursor
        if max_results is not None:
            ctx_modifiers["maxResults"] = max_results
        if all_pages:
            ctx_modifiers["allPages"] = True

        cmd_context = CommandContext(
            name="interaction ls",
            inputs={},
            modifiers=ctx_modifiers,
        )

        parsed_type = parse_choice(
            interaction_type,
            _INTERACTION_TYPE_MAP,
            label="interaction type",
        )
        start_value = parse_iso_datetime(start_time, label="start-time") if start_time else None
        end_value = parse_iso_datetime(end_time, label="end-time") if end_time else None
        person_id_value = PersonId(person_id) if person_id is not None else None
        company_id_value = CompanyId(company_id) if company_id is not None else None
        opportunity_id_value = OpportunityId(opportunity_id) if opportunity_id is not None else None

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

            while True:
                page = client.interactions.list(
                    type=parsed_type,
                    start_time=start_value,
                    end_time=end_value,
                    person_id=person_id_value,
                    company_id=company_id_value,
                    opportunity_id=opportunity_id_value,
                    page_size=page_size,
                    page_token=page_token,
                )

                for idx, interaction in enumerate(page.data):
                    results.append(_interaction_payload(interaction))
                    if progress and task_id is not None:
                        progress.update(task_id, completed=len(results))
                    if max_results is not None and len(results) >= max_results:
                        stopped_mid_page = idx < (len(page.data) - 1)
                        if stopped_mid_page:
                            warnings.append(
                                "Results limited by --max-results. Use --all to fetch all results."
                            )
                        pagination = None
                        if page.next_page_token and not stopped_mid_page:
                            pagination = {
                                "interactions": {
                                    "nextCursor": page.next_page_token,
                                    "prevCursor": None,
                                }
                            }
                        return CommandOutput(
                            data={"interactions": results[:max_results]},
                            context=cmd_context,
                            pagination=pagination,
                            api_called=True,
                        )

                if first_page and not all_pages and max_results is None:
                    pagination = (
                        {
                            "interactions": {
                                "nextCursor": page.next_page_token,
                                "prevCursor": None,
                            }
                        }
                        if page.next_page_token
                        else None
                    )
                    return CommandOutput(
                        data={"interactions": results},
                        context=cmd_context,
                        pagination=pagination,
                        api_called=True,
                    )
                first_page = False

                page_token = page.next_page_token
                if not page_token:
                    break

        return CommandOutput(
            data={"interactions": results},
            context=cmd_context,
            pagination=None,
            api_called=True,
        )

    run_command(ctx, command="interaction ls", fn=fn)


@category("read")
@interaction_group.command(name="get", cls=RichCommand)
@click.argument("interaction_id", type=int)
@click.option(
    "--type",
    "-t",
    "interaction_type",
    type=click.Choice(sorted(_INTERACTION_TYPE_MAP.keys())),
    required=True,
    help="Interaction type (required by API).",
)
@output_options
@click.pass_obj
def interaction_get(ctx: CLIContext, interaction_id: int, *, interaction_type: str) -> None:
    """Get an interaction by id.

    The --type flag is required because the Affinity API stores interactions
    in type-specific tables.

    Examples:

    - `xaffinity interaction get 123 --type meeting`
    - `xaffinity interaction get 456 -t email`
    """

    def fn(ctx: CLIContext, warnings: list[str]) -> CommandOutput:
        parsed_type = parse_choice(
            interaction_type,
            _INTERACTION_TYPE_MAP,
            label="interaction type",
        )
        if parsed_type is None:
            raise CLIError("Missing interaction type.", error_type="usage_error", exit_code=2)
        client = ctx.get_client(warnings=warnings)
        interaction = client.interactions.get(InteractionId(interaction_id), parsed_type)

        cmd_context = CommandContext(
            name="interaction get",
            inputs={"interactionId": interaction_id},
            modifiers={"type": interaction_type},
        )

        return CommandOutput(
            data={"interaction": _interaction_payload(interaction)},
            context=cmd_context,
            api_called=True,
        )

    run_command(ctx, command="interaction get", fn=fn)


@category("write")
@interaction_group.command(name="create", cls=RichCommand)
@click.option(
    "--type",
    "-t",
    "interaction_type",
    type=click.Choice(sorted(_INTERACTION_TYPE_MAP.keys())),
    required=True,
    help="Interaction type (required).",
)
@click.option("--person-id", "person_ids", multiple=True, type=int, help="Person id.")
@click.option("--content", type=str, required=True, help="Interaction content.")
@click.option("--date", type=str, required=True, help="Interaction date (ISO-8601).")
@click.option(
    "--direction",
    type=click.Choice(sorted(_INTERACTION_DIRECTION_MAP.keys())),
    default=None,
    help="Direction (incoming, outgoing).",
)
@output_options
@click.pass_obj
def interaction_create(
    ctx: CLIContext,
    *,
    interaction_type: str,
    person_ids: tuple[int, ...],
    content: str,
    date: str,
    direction: str | None,
) -> None:
    """Create an interaction."""

    def fn(ctx: CLIContext, warnings: list[str]) -> CommandOutput:
        if not person_ids:
            raise CLIError(
                "At least one --person-id is required.",
                error_type="usage_error",
                exit_code=2,
            )

        parsed_type = parse_choice(
            interaction_type,
            _INTERACTION_TYPE_MAP,
            label="interaction type",
        )
        if parsed_type is None:
            raise CLIError("Missing interaction type.", error_type="usage_error", exit_code=2)
        parsed_direction = parse_choice(direction, _INTERACTION_DIRECTION_MAP, label="direction")
        date_value = parse_iso_datetime(date, label="date")

        client = ctx.get_client(warnings=warnings)
        interaction = client.interactions.create(
            InteractionCreate(
                type=parsed_type,
                person_ids=[PersonId(pid) for pid in person_ids],
                content=content,
                date=date_value,
                direction=parsed_direction,
            )
        )

        # Build CommandContext for interaction create
        ctx_modifiers: dict[str, object] = {
            "type": interaction_type,
            "personIds": list(person_ids),
            "date": date,
        }
        if direction:
            ctx_modifiers["direction"] = direction

        cmd_context = CommandContext(
            name="interaction create",
            inputs={"type": interaction_type},
            modifiers=ctx_modifiers,
        )

        return CommandOutput(
            data={"interaction": _interaction_payload(interaction)},
            context=cmd_context,
            api_called=True,
        )

    run_command(ctx, command="interaction create", fn=fn)


@category("write")
@interaction_group.command(name="update", cls=RichCommand)
@click.argument("interaction_id", type=int)
@click.option(
    "--type",
    "-t",
    "interaction_type",
    type=click.Choice(sorted(_INTERACTION_TYPE_MAP.keys())),
    required=True,
    help="Interaction type (required by API).",
)
@click.option("--person-id", "person_ids", multiple=True, type=int, help="Person id.")
@click.option("--content", type=str, default=None, help="Interaction content.")
@click.option("--date", type=str, default=None, help="Interaction date (ISO-8601).")
@click.option(
    "--direction",
    type=click.Choice(sorted(_INTERACTION_DIRECTION_MAP.keys())),
    default=None,
    help="Direction (incoming, outgoing).",
)
@output_options
@click.pass_obj
def interaction_update(
    ctx: CLIContext,
    interaction_id: int,
    *,
    interaction_type: str,
    person_ids: tuple[int, ...],
    content: str | None,
    date: str | None,
    direction: str | None,
) -> None:
    """Update an interaction."""

    def fn(ctx: CLIContext, warnings: list[str]) -> CommandOutput:
        parsed_type = parse_choice(
            interaction_type,
            _INTERACTION_TYPE_MAP,
            label="interaction type",
        )
        if parsed_type is None:
            raise CLIError("Missing interaction type.", error_type="usage_error", exit_code=2)

        parsed_direction = parse_choice(direction, _INTERACTION_DIRECTION_MAP, label="direction")
        date_value = parse_iso_datetime(date, label="date") if date else None

        if not (person_ids or content or date_value or parsed_direction is not None):
            raise CLIError(
                "Provide at least one field to update.",
                error_type="usage_error",
                exit_code=2,
                hint="Use --person-id, --content, --date, or --direction.",
            )

        client = ctx.get_client(warnings=warnings)
        interaction = client.interactions.update(
            InteractionId(interaction_id),
            parsed_type,
            InteractionUpdate(
                person_ids=[PersonId(pid) for pid in person_ids] if person_ids else None,
                content=content,
                date=date_value,
                direction=parsed_direction,
            ),
        )

        # Build CommandContext for interaction update
        ctx_modifiers: dict[str, object] = {"type": interaction_type}
        if person_ids:
            ctx_modifiers["personIds"] = list(person_ids)
        if content:
            ctx_modifiers["content"] = content
        if date:
            ctx_modifiers["date"] = date
        if direction:
            ctx_modifiers["direction"] = direction

        cmd_context = CommandContext(
            name="interaction update",
            inputs={"interactionId": interaction_id},
            modifiers=ctx_modifiers,
        )

        return CommandOutput(
            data={"interaction": _interaction_payload(interaction)},
            context=cmd_context,
            api_called=True,
        )

    run_command(ctx, command="interaction update", fn=fn)


@category("write")
@destructive
@interaction_group.command(name="delete", cls=RichCommand)
@click.argument("interaction_id", type=int)
@click.option(
    "--type",
    "-t",
    "interaction_type",
    type=click.Choice(sorted(_INTERACTION_TYPE_MAP.keys())),
    required=True,
    help="Interaction type (required by API).",
)
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt.")
@output_options
@click.pass_obj
def interaction_delete(
    ctx: CLIContext, interaction_id: int, *, interaction_type: str, yes: bool
) -> None:
    """Delete an interaction."""
    if not yes:
        click.confirm(f"Delete interaction {interaction_id}?", abort=True)

    def fn(ctx: CLIContext, warnings: list[str]) -> CommandOutput:
        parsed_type = parse_choice(
            interaction_type,
            _INTERACTION_TYPE_MAP,
            label="interaction type",
        )
        if parsed_type is None:
            raise CLIError("Missing interaction type.", error_type="usage_error", exit_code=2)
        client = ctx.get_client(warnings=warnings)
        success = client.interactions.delete(InteractionId(interaction_id), parsed_type)

        cmd_context = CommandContext(
            name="interaction delete",
            inputs={"interactionId": interaction_id},
            modifiers={"type": interaction_type},
        )

        return CommandOutput(
            data={"success": success},
            context=cmd_context,
            api_called=True,
        )

    run_command(ctx, command="interaction delete", fn=fn)
