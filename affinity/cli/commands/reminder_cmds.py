from __future__ import annotations

from typing import Any

from affinity.models.secondary import Reminder, ReminderCreate, ReminderUpdate
from affinity.models.types import ReminderResetType, ReminderStatus, ReminderType
from affinity.types import CompanyId, OpportunityId, PersonId, ReminderIdType, UserId

from ..click_compat import RichCommand, RichGroup, click
from ..context import CLIContext
from ..errors import CLIError
from ..options import output_options
from ..runner import CommandOutput, run_command
from ._v1_parsing import parse_choice, parse_iso_datetime


@click.group(name="reminder", cls=RichGroup)
def reminder_group() -> None:
    """Reminder commands."""


_REMINDER_TYPE_MAP = {
    "one-time": ReminderType.ONE_TIME,
    "recurring": ReminderType.RECURRING,
}

_REMINDER_RESET_MAP = {
    "interaction": ReminderResetType.INTERACTION,
    "email": ReminderResetType.EMAIL,
    "meeting": ReminderResetType.MEETING,
}

_REMINDER_STATUS_MAP = {
    "active": ReminderStatus.ACTIVE,
    "completed": ReminderStatus.COMPLETED,
    "overdue": ReminderStatus.OVERDUE,
}


def _extract_id(value: Any) -> int | None:
    if value is None:
        return None
    if hasattr(value, "id"):
        try:
            return int(value.id)
        except Exception:
            return None
    if isinstance(value, dict):
        for key in (
            "id",
            "personId",
            "organizationId",
            "companyId",
            "opportunityId",
            "person_id",
            "organization_id",
            "company_id",
            "opportunity_id",
        ):
            raw = value.get(key)
            if raw is None:
                continue
            if isinstance(raw, bool):
                continue
            if isinstance(raw, (int, float)):
                return int(raw)
            if isinstance(raw, str) and raw.isdigit():
                return int(raw)
    return None


def _reminder_payload(reminder: Reminder) -> dict[str, object]:
    return {
        "id": int(reminder.id),
        "type": int(reminder.type),
        "status": int(reminder.status),
        "content": reminder.content,
        "dueDate": reminder.due_date,
        "resetType": int(reminder.reset_type) if reminder.reset_type is not None else None,
        "reminderDays": reminder.reminder_days,
        "ownerId": _extract_id(reminder.owner),
        "creatorId": _extract_id(reminder.creator),
        "completerId": _extract_id(reminder.completer),
        "personId": _extract_id(reminder.person),
        "companyId": _extract_id(reminder.organization),
        "opportunityId": _extract_id(reminder.opportunity),
        "createdAt": reminder.created_at,
        "completedAt": reminder.completed_at,
    }


def _validate_single_entity(
    person_id: int | None,
    company_id: int | None,
    opportunity_id: int | None,
) -> None:
    count = sum(1 for value in (person_id, company_id, opportunity_id) if value is not None)
    if count > 1:
        raise CLIError(
            "Reminders can be associated with only one entity.",
            error_type="usage_error",
            exit_code=2,
            hint="Provide only one of --person-id, --company-id, or --opportunity-id.",
        )


@reminder_group.command(name="ls", cls=RichCommand)
@click.option("--person-id", type=int, default=None, help="Filter by person id.")
@click.option("--company-id", type=int, default=None, help="Filter by company id.")
@click.option("--opportunity-id", type=int, default=None, help="Filter by opportunity id.")
@click.option("--creator-id", type=int, default=None, help="Filter by creator id.")
@click.option("--owner-id", type=int, default=None, help="Filter by owner id.")
@click.option("--completer-id", type=int, default=None, help="Filter by completer id.")
@click.option(
    "--type",
    "reminder_type",
    type=click.Choice(sorted(_REMINDER_TYPE_MAP.keys())),
    default=None,
    help="Reminder type (one-time, recurring).",
)
@click.option(
    "--reset-type",
    type=click.Choice(sorted(_REMINDER_RESET_MAP.keys())),
    default=None,
    help="Reset type for recurring reminders.",
)
@click.option(
    "--status",
    type=click.Choice(sorted(_REMINDER_STATUS_MAP.keys())),
    default=None,
    help="Reminder status (active, completed, overdue).",
)
@click.option("--due-before", type=str, default=None, help="Due before (ISO-8601).")
@click.option("--due-after", type=str, default=None, help="Due after (ISO-8601).")
@click.option("--page-size", type=int, default=None, help="Page size (max 500).")
@click.option("--cursor", type=str, default=None, help="Resume from a prior cursor.")
@click.option("--max-results", type=int, default=None, help="Stop after N results total.")
@click.option("--all", "all_pages", is_flag=True, help="Fetch all pages.")
@output_options
@click.pass_obj
def reminder_ls(
    ctx: CLIContext,
    *,
    person_id: int | None,
    company_id: int | None,
    opportunity_id: int | None,
    creator_id: int | None,
    owner_id: int | None,
    completer_id: int | None,
    reminder_type: str | None,
    reset_type: str | None,
    status: str | None,
    due_before: str | None,
    due_after: str | None,
    page_size: int | None,
    cursor: str | None,
    max_results: int | None,
    all_pages: bool,
) -> None:
    """List reminders (v1)."""

    def fn(ctx: CLIContext, warnings: list[str]) -> CommandOutput:
        client = ctx.get_client(warnings=warnings)
        results: list[dict[str, object]] = []
        first_page = True
        page_token = cursor

        parsed_type = parse_choice(reminder_type, _REMINDER_TYPE_MAP, label="reminder type")
        parsed_reset = parse_choice(reset_type, _REMINDER_RESET_MAP, label="reset type")
        parsed_status = parse_choice(status, _REMINDER_STATUS_MAP, label="status")
        due_before_value = (
            parse_iso_datetime(due_before, label="due-before") if due_before else None
        )
        due_after_value = parse_iso_datetime(due_after, label="due-after") if due_after else None
        person_id_value = PersonId(person_id) if person_id is not None else None
        company_id_value = CompanyId(company_id) if company_id is not None else None
        opportunity_id_value = OpportunityId(opportunity_id) if opportunity_id is not None else None
        creator_id_value = UserId(creator_id) if creator_id is not None else None
        owner_id_value = UserId(owner_id) if owner_id is not None else None
        completer_id_value = UserId(completer_id) if completer_id is not None else None

        while True:
            page = client.reminders.list(
                person_id=person_id_value,
                organization_id=company_id_value,
                opportunity_id=opportunity_id_value,
                creator_id=creator_id_value,
                owner_id=owner_id_value,
                completer_id=completer_id_value,
                type=parsed_type,
                reset_type=parsed_reset,
                status=parsed_status,
                due_before=due_before_value,
                due_after=due_after_value,
                page_size=page_size,
                page_token=page_token,
            )

            for idx, reminder in enumerate(page.data):
                results.append(_reminder_payload(reminder))
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
                            "reminders": {"nextCursor": page.next_page_token, "prevCursor": None}
                        }
                    return CommandOutput(
                        data={"reminders": results[:max_results]},
                        pagination=pagination,
                        api_called=True,
                    )

            if first_page and not all_pages and max_results is None:
                pagination = (
                    {"reminders": {"nextCursor": page.next_page_token, "prevCursor": None}}
                    if page.next_page_token
                    else None
                )
                return CommandOutput(
                    data={"reminders": results}, pagination=pagination, api_called=True
                )
            first_page = False

            page_token = page.next_page_token
            if not page_token:
                break

        return CommandOutput(data={"reminders": results}, pagination=None, api_called=True)

    run_command(ctx, command="reminder ls", fn=fn)


@reminder_group.command(name="get", cls=RichCommand)
@click.argument("reminder_id", type=int)
@output_options
@click.pass_obj
def reminder_get(ctx: CLIContext, reminder_id: int) -> None:
    """Get a reminder by id (v1)."""

    def fn(ctx: CLIContext, warnings: list[str]) -> CommandOutput:
        client = ctx.get_client(warnings=warnings)
        reminder = client.reminders.get(ReminderIdType(reminder_id))
        return CommandOutput(data={"reminder": _reminder_payload(reminder)}, api_called=True)

    run_command(ctx, command="reminder get", fn=fn)


@reminder_group.command(name="create", cls=RichCommand)
@click.option("--owner-id", type=int, required=True, help="Owner id (required).")
@click.option(
    "--type",
    "reminder_type",
    type=click.Choice(sorted(_REMINDER_TYPE_MAP.keys())),
    required=True,
    help="Reminder type (one-time, recurring).",
)
@click.option("--content", type=str, default=None, help="Reminder content.")
@click.option("--due-date", type=str, default=None, help="Due date (ISO-8601).")
@click.option(
    "--reset-type",
    type=click.Choice(sorted(_REMINDER_RESET_MAP.keys())),
    default=None,
    help="Reset type for recurring reminders.",
)
@click.option("--reminder-days", type=int, default=None, help="Days before due date to remind.")
@click.option("--person-id", type=int, default=None, help="Associate person id.")
@click.option("--company-id", type=int, default=None, help="Associate company id.")
@click.option("--opportunity-id", type=int, default=None, help="Associate opportunity id.")
@output_options
@click.pass_obj
def reminder_create(
    ctx: CLIContext,
    *,
    owner_id: int,
    reminder_type: str,
    content: str | None,
    due_date: str | None,
    reset_type: str | None,
    reminder_days: int | None,
    person_id: int | None,
    company_id: int | None,
    opportunity_id: int | None,
) -> None:
    """Create a reminder (v1)."""

    def fn(ctx: CLIContext, warnings: list[str]) -> CommandOutput:
        _ = warnings
        _validate_single_entity(person_id, company_id, opportunity_id)

        parsed_type = parse_choice(reminder_type, _REMINDER_TYPE_MAP, label="reminder type")
        if parsed_type is None:
            raise CLIError("Missing reminder type.", error_type="usage_error", exit_code=2)
        parsed_reset = parse_choice(reset_type, _REMINDER_RESET_MAP, label="reset type")
        due_date_value = parse_iso_datetime(due_date, label="due-date") if due_date else None

        client = ctx.get_client(warnings=warnings)
        reminder = client.reminders.create(
            ReminderCreate(
                owner_id=UserId(owner_id),
                type=parsed_type,
                content=content,
                due_date=due_date_value,
                reset_type=parsed_reset,
                reminder_days=reminder_days,
                person_id=PersonId(person_id) if person_id is not None else None,
                organization_id=CompanyId(company_id) if company_id is not None else None,
                opportunity_id=OpportunityId(opportunity_id)
                if opportunity_id is not None
                else None,
            )
        )
        return CommandOutput(data={"reminder": _reminder_payload(reminder)}, api_called=True)

    run_command(ctx, command="reminder create", fn=fn)


@reminder_group.command(name="update", cls=RichCommand)
@click.argument("reminder_id", type=int)
@click.option("--owner-id", type=int, default=None, help="Owner id.")
@click.option(
    "--type",
    "reminder_type",
    type=click.Choice(sorted(_REMINDER_TYPE_MAP.keys())),
    default=None,
    help="Reminder type (one-time, recurring).",
)
@click.option("--content", type=str, default=None, help="Reminder content.")
@click.option("--due-date", type=str, default=None, help="Due date (ISO-8601).")
@click.option(
    "--reset-type",
    type=click.Choice(sorted(_REMINDER_RESET_MAP.keys())),
    default=None,
    help="Reset type for recurring reminders.",
)
@click.option("--reminder-days", type=int, default=None, help="Days before due date to remind.")
@click.option("--completed", is_flag=True, help="Mark reminder as completed.")
@click.option("--not-completed", is_flag=True, help="Mark reminder as not completed.")
@output_options
@click.pass_obj
def reminder_update(
    ctx: CLIContext,
    reminder_id: int,
    *,
    owner_id: int | None,
    reminder_type: str | None,
    content: str | None,
    due_date: str | None,
    reset_type: str | None,
    reminder_days: int | None,
    completed: bool,
    not_completed: bool,
) -> None:
    """Update a reminder (v1)."""

    def fn(ctx: CLIContext, warnings: list[str]) -> CommandOutput:
        if completed and not_completed:
            raise CLIError(
                "--completed and --not-completed cannot be used together.",
                error_type="usage_error",
                exit_code=2,
            )

        parsed_type = parse_choice(reminder_type, _REMINDER_TYPE_MAP, label="reminder type")
        parsed_reset = parse_choice(reset_type, _REMINDER_RESET_MAP, label="reset type")
        due_date_value = parse_iso_datetime(due_date, label="due-date") if due_date else None

        is_completed: bool | None = None
        if completed:
            is_completed = True
        if not_completed:
            is_completed = False

        client = ctx.get_client(warnings=warnings)
        reminder = client.reminders.update(
            ReminderIdType(reminder_id),
            ReminderUpdate(
                owner_id=UserId(owner_id) if owner_id is not None else None,
                type=parsed_type,
                content=content,
                due_date=due_date_value,
                reset_type=parsed_reset,
                reminder_days=reminder_days,
                is_completed=is_completed,
            ),
        )
        return CommandOutput(data={"reminder": _reminder_payload(reminder)}, api_called=True)

    run_command(ctx, command="reminder update", fn=fn)


@reminder_group.command(name="delete", cls=RichCommand)
@click.argument("reminder_id", type=int)
@output_options
@click.pass_obj
def reminder_delete(ctx: CLIContext, reminder_id: int) -> None:
    """Delete a reminder (v1)."""

    def fn(ctx: CLIContext, warnings: list[str]) -> CommandOutput:
        client = ctx.get_client(warnings=warnings)
        success = client.reminders.delete(ReminderIdType(reminder_id))
        return CommandOutput(data={"success": success}, api_called=True)

    run_command(ctx, command="reminder delete", fn=fn)
