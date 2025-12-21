from __future__ import annotations

from affinity.models.secondary import Interaction, InteractionCreate, InteractionUpdate
from affinity.models.types import InteractionDirection, InteractionType
from affinity.types import InteractionId, PersonId

from ..click_compat import RichCommand, RichGroup, click
from ..context import CLIContext
from ..errors import CLIError
from ..options import output_options
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
    return {
        "id": int(interaction.id),
        "type": int(interaction.type),
        "date": interaction.date,
        "direction": int(interaction.direction) if interaction.direction is not None else None,
        "title": interaction.title,
        "subject": interaction.subject,
        "startTime": interaction.start_time,
        "endTime": interaction.end_time,
        "personIds": [int(p.id) for p in interaction.persons],
        "attendees": interaction.attendees,
        "notes": [int(n) for n in interaction.notes],
    }


@interaction_group.command(name="ls", cls=RichCommand)
@click.option(
    "--type",
    "interaction_type",
    type=click.Choice(sorted(_INTERACTION_TYPE_MAP.keys())),
    default=None,
    help="Interaction type (meeting, call, chat-message, email).",
)
@click.option("--start-time", type=str, default=None, help="Start time (ISO-8601).")
@click.option("--end-time", type=str, default=None, help="End time (ISO-8601).")
@click.option("--person-id", type=int, default=None, help="Filter by person id.")
@click.option("--page-size", type=int, default=None, help="Page size (max 500).")
@click.option("--cursor", type=str, default=None, help="Resume from a prior cursor.")
@click.option("--max-results", type=int, default=None, help="Stop after N results total.")
@click.option("--all", "all_pages", is_flag=True, help="Fetch all pages.")
@output_options
@click.pass_obj
def interaction_ls(
    ctx: CLIContext,
    *,
    interaction_type: str | None,
    start_time: str | None,
    end_time: str | None,
    person_id: int | None,
    page_size: int | None,
    cursor: str | None,
    max_results: int | None,
    all_pages: bool,
) -> None:
    """List interactions (v1)."""

    def fn(ctx: CLIContext, warnings: list[str]) -> CommandOutput:
        client = ctx.get_client(warnings=warnings)
        results: list[dict[str, object]] = []
        first_page = True
        page_token = cursor

        parsed_type = parse_choice(
            interaction_type,
            _INTERACTION_TYPE_MAP,
            label="interaction type",
        )
        start_value = parse_iso_datetime(start_time, label="start-time") if start_time else None
        end_value = parse_iso_datetime(end_time, label="end-time") if end_time else None
        person_id_value = PersonId(person_id) if person_id is not None else None

        while True:
            page = client.interactions.list(
                type=parsed_type,
                start_time=start_value,
                end_time=end_value,
                person_id=person_id_value,
                page_size=page_size,
                page_token=page_token,
            )

            for idx, interaction in enumerate(page.data):
                results.append(_interaction_payload(interaction))
                if max_results is not None and len(results) >= max_results:
                    stopped_mid_page = idx < (len(page.data) - 1)
                    if stopped_mid_page:
                        warnings.append(
                            "Results truncated mid-page; resume cursor omitted "
                            "to avoid skipping items. Re-run with a higher "
                            "--max-results or without it to paginate safely."
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
                    data={"interactions": results}, pagination=pagination, api_called=True
                )
            first_page = False

            page_token = page.next_page_token
            if not page_token:
                break

        return CommandOutput(data={"interactions": results}, pagination=None, api_called=True)

    run_command(ctx, command="interaction ls", fn=fn)


@interaction_group.command(name="get", cls=RichCommand)
@click.argument("interaction_id", type=int)
@click.option(
    "--type",
    "interaction_type",
    type=click.Choice(sorted(_INTERACTION_TYPE_MAP.keys())),
    required=True,
    help="Interaction type (meeting, call, chat-message, email).",
)
@output_options
@click.pass_obj
def interaction_get(ctx: CLIContext, interaction_id: int, *, interaction_type: str) -> None:
    """Get an interaction by id (v1)."""

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
        return CommandOutput(
            data={"interaction": _interaction_payload(interaction)}, api_called=True
        )

    run_command(ctx, command="interaction get", fn=fn)


@interaction_group.command(name="create", cls=RichCommand)
@click.option(
    "--type",
    "interaction_type",
    type=click.Choice(sorted(_INTERACTION_TYPE_MAP.keys())),
    required=True,
    help="Interaction type (meeting, call, chat-message, email).",
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
    """Create an interaction (v1)."""

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
        return CommandOutput(
            data={"interaction": _interaction_payload(interaction)}, api_called=True
        )

    run_command(ctx, command="interaction create", fn=fn)


@interaction_group.command(name="update", cls=RichCommand)
@click.argument("interaction_id", type=int)
@click.option(
    "--type",
    "interaction_type",
    type=click.Choice(sorted(_INTERACTION_TYPE_MAP.keys())),
    required=True,
    help="Interaction type (meeting, call, chat-message, email).",
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
    """Update an interaction (v1)."""

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
        return CommandOutput(
            data={"interaction": _interaction_payload(interaction)}, api_called=True
        )

    run_command(ctx, command="interaction update", fn=fn)


@interaction_group.command(name="delete", cls=RichCommand)
@click.argument("interaction_id", type=int)
@click.option(
    "--type",
    "interaction_type",
    type=click.Choice(sorted(_INTERACTION_TYPE_MAP.keys())),
    required=True,
    help="Interaction type (meeting, call, chat-message, email).",
)
@output_options
@click.pass_obj
def interaction_delete(ctx: CLIContext, interaction_id: int, *, interaction_type: str) -> None:
    """Delete an interaction (v1)."""

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
        return CommandOutput(data={"success": success}, api_called=True)

    run_command(ctx, command="interaction delete", fn=fn)
