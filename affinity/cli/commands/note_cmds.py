from __future__ import annotations

from affinity.models.secondary import Note, NoteCreate, NoteUpdate
from affinity.models.types import NoteType
from affinity.types import CompanyId, NoteId, OpportunityId, PersonId, UserId

from ..click_compat import RichCommand, RichGroup, click
from ..context import CLIContext
from ..errors import CLIError
from ..options import output_options
from ..runner import CommandOutput, run_command
from ._v1_parsing import parse_choice, parse_iso_datetime


@click.group(name="note", cls=RichGroup)
def note_group() -> None:
    """Note commands."""


_NOTE_TYPE_MAP = {
    "plain-text": NoteType.PLAIN_TEXT,
    "plain": NoteType.PLAIN_TEXT,
    "html": NoteType.HTML,
    "ai-notetaker": NoteType.AI_NOTETAKER,
    "email-derived": NoteType.EMAIL_DERIVED,
}


def _note_payload(note: Note) -> dict[str, object]:
    return {
        "id": int(note.id),
        "type": int(note.type),
        "creatorId": int(note.creator_id),
        "content": note.content,
        "personIds": [int(p) for p in note.person_ids],
        "associatedPersonIds": [int(p) for p in note.associated_person_ids],
        "interactionPersonIds": [int(p) for p in note.interaction_person_ids],
        "mentionedPersonIds": [int(p) for p in note.mentioned_person_ids],
        "companyIds": [int(o) for o in note.company_ids],
        "opportunityIds": [int(o) for o in note.opportunity_ids],
        "interactionId": note.interaction_id,
        "interactionType": int(note.interaction_type) if note.interaction_type else None,
        "isMeeting": note.is_meeting,
        "parentId": int(note.parent_id) if note.parent_id else None,
        "createdAt": note.created_at,
        "updatedAt": note.updated_at,
    }


@note_group.command(name="ls", cls=RichCommand)
@click.option("--person-id", type=int, default=None, help="Filter by person id.")
@click.option("--company-id", type=int, default=None, help="Filter by company id.")
@click.option("--opportunity-id", type=int, default=None, help="Filter by opportunity id.")
@click.option("--creator-id", type=int, default=None, help="Filter by creator id.")
@click.option("--page-size", type=int, default=None, help="Page size (max 500).")
@click.option("--cursor", type=str, default=None, help="Resume from a prior cursor.")
@click.option("--max-results", type=int, default=None, help="Stop after N results total.")
@click.option("--all", "all_pages", is_flag=True, help="Fetch all pages.")
@output_options
@click.pass_obj
def note_ls(
    ctx: CLIContext,
    *,
    person_id: int | None,
    company_id: int | None,
    opportunity_id: int | None,
    creator_id: int | None,
    page_size: int | None,
    cursor: str | None,
    max_results: int | None,
    all_pages: bool,
) -> None:
    """
    List notes.

    Examples:

    - `affinity note ls --person-id 12345`
    - `affinity note ls --company-id 67890 --all`
    - `affinity note ls --creator-id 111 --max-results 50`
    """

    def fn(ctx: CLIContext, warnings: list[str]) -> CommandOutput:
        client = ctx.get_client(warnings=warnings)
        results: list[dict[str, object]] = []
        first_page = True
        page_token = cursor
        person_id_value = PersonId(person_id) if person_id is not None else None
        company_id_value = CompanyId(company_id) if company_id is not None else None
        opportunity_id_value = OpportunityId(opportunity_id) if opportunity_id is not None else None
        creator_id_value = UserId(creator_id) if creator_id is not None else None
        while True:
            page = client.notes.list(
                person_id=person_id_value,
                company_id=company_id_value,
                opportunity_id=opportunity_id_value,
                creator_id=creator_id_value,
                page_size=page_size,
                page_token=page_token,
            )

            for idx, note in enumerate(page.data):
                results.append(_note_payload(note))
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
                            "notes": {"nextCursor": page.next_page_token, "prevCursor": None}
                        }
                    return CommandOutput(
                        data={"notes": results[:max_results]},
                        pagination=pagination,
                        api_called=True,
                    )

            if first_page and not all_pages and max_results is None:
                pagination = (
                    {"notes": {"nextCursor": page.next_page_token, "prevCursor": None}}
                    if page.next_page_token
                    else None
                )
                return CommandOutput(
                    data={"notes": results}, pagination=pagination, api_called=True
                )
            first_page = False

            page_token = page.next_page_token
            if not page_token:
                break

        return CommandOutput(data={"notes": results}, pagination=None, api_called=True)

    run_command(ctx, command="note ls", fn=fn)


@note_group.command(name="get", cls=RichCommand)
@click.argument("note_id", type=int)
@output_options
@click.pass_obj
def note_get(ctx: CLIContext, note_id: int) -> None:
    """
    Get a note by id.

    Example: `affinity note get 12345`
    """

    def fn(ctx: CLIContext, warnings: list[str]) -> CommandOutput:
        client = ctx.get_client(warnings=warnings)
        note = client.notes.get(NoteId(note_id))
        return CommandOutput(data={"note": _note_payload(note)}, api_called=True)

    run_command(ctx, command="note get", fn=fn)


@note_group.command(name="create", cls=RichCommand)
@click.option("--content", type=str, required=True, help="Note content.")
@click.option(
    "--type",
    "note_type",
    type=click.Choice(sorted(_NOTE_TYPE_MAP.keys())),
    default=None,
    help="Note type (plain-text, html, ai-notetaker, email-derived).",
)
@click.option("--person-id", "person_ids", multiple=True, type=int, help="Associate person id.")
@click.option(
    "--company-id",
    "company_ids",
    multiple=True,
    type=int,
    help="Associate company id.",
)
@click.option(
    "--opportunity-id",
    "opportunity_ids",
    multiple=True,
    type=int,
    help="Associate opportunity id.",
)
@click.option("--parent-id", type=int, default=None, help="Parent note id (reply).")
@click.option("--creator-id", type=int, default=None, help="Creator id override.")
@click.option(
    "--created-at",
    type=str,
    default=None,
    help="Creation timestamp (ISO-8601).",
)
@output_options
@click.pass_obj
def note_create(
    ctx: CLIContext,
    *,
    content: str,
    note_type: str | None,
    person_ids: tuple[int, ...],
    company_ids: tuple[int, ...],
    opportunity_ids: tuple[int, ...],
    parent_id: int | None,
    creator_id: int | None,
    created_at: str | None,
) -> None:
    """
    Create a note attached to an entity.

    Examples:

    - `affinity note create --content "Meeting notes" --person-id 12345`
    - `affinity note create --content "<b>Summary</b>" --type html --company-id 67890`
    """

    def fn(ctx: CLIContext, warnings: list[str]) -> CommandOutput:
        _ = warnings
        if not (person_ids or company_ids or opportunity_ids or parent_id):
            raise CLIError(
                "Notes must be attached to at least one entity or parent note.",
                exit_code=2,
                error_type="usage_error",
                hint="Provide --person-id/--company-id/--opportunity-id or --parent-id.",
            )

        parsed_type = parse_choice(note_type, _NOTE_TYPE_MAP, label="note type")
        created_at_value = (
            parse_iso_datetime(created_at, label="created-at") if created_at else None
        )

        client = ctx.get_client(warnings=warnings)
        note = client.notes.create(
            NoteCreate(
                content=content,
                type=parsed_type or NoteType.PLAIN_TEXT,
                person_ids=[PersonId(pid) for pid in person_ids],
                company_ids=[CompanyId(cid) for cid in company_ids],
                opportunity_ids=[OpportunityId(oid) for oid in opportunity_ids],
                parent_id=NoteId(parent_id) if parent_id else None,
                creator_id=UserId(creator_id) if creator_id is not None else None,
                created_at=created_at_value,
            )
        )
        return CommandOutput(data={"note": _note_payload(note)}, api_called=True)

    run_command(ctx, command="note create", fn=fn)


@note_group.command(name="update", cls=RichCommand)
@click.argument("note_id", type=int)
@click.option("--content", type=str, required=True, help="Updated note content.")
@output_options
@click.pass_obj
def note_update(ctx: CLIContext, note_id: int, *, content: str) -> None:
    """Update a note (v1)."""

    def fn(ctx: CLIContext, warnings: list[str]) -> CommandOutput:
        client = ctx.get_client(warnings=warnings)
        note = client.notes.update(NoteId(note_id), NoteUpdate(content=content))
        return CommandOutput(data={"note": _note_payload(note)}, api_called=True)

    run_command(ctx, command="note update", fn=fn)


@note_group.command(name="delete", cls=RichCommand)
@click.argument("note_id", type=int)
@output_options
@click.pass_obj
def note_delete(ctx: CLIContext, note_id: int) -> None:
    """Delete a note (v1)."""

    def fn(ctx: CLIContext, warnings: list[str]) -> CommandOutput:
        client = ctx.get_client(warnings=warnings)
        success = client.notes.delete(NoteId(note_id))
        return CommandOutput(data={"success": success}, api_called=True)

    run_command(ctx, command="note delete", fn=fn)
