from __future__ import annotations

from affinity.models.entities import FieldValueChange
from affinity.types import (
    CompanyId,
    FieldId,
    FieldValueChangeAction,
    ListEntryId,
    OpportunityId,
    PersonId,
)

from ..click_compat import RichCommand, RichGroup, click
from ..context import CLIContext
from ..errors import CLIError
from ..options import output_options
from ..runner import CommandOutput, run_command
from ..serialization import serialize_model_for_cli


@click.group(name="field-value-changes", cls=RichGroup)
def field_value_changes_group() -> None:
    """Field value change history commands."""


def _field_value_change_payload(item: FieldValueChange) -> dict[str, object]:
    # Serializes field value change with proper datetime handling
    payload = serialize_model_for_cli(item)
    # Convert enum value back to name for CLI display
    if "actionType" in payload:
        payload["actionType"] = FieldValueChangeAction(payload["actionType"]).name.lower()
    return payload


_ACTION_TYPE_MAP = {
    "create": FieldValueChangeAction.CREATE,
    "delete": FieldValueChangeAction.DELETE,
    "update": FieldValueChangeAction.UPDATE,
}


def _validate_exactly_one_selector(
    person_id: int | None,
    company_id: int | None,
    opportunity_id: int | None,
    list_entry_id: int | None,
) -> None:
    count = sum(1 for v in (person_id, company_id, opportunity_id, list_entry_id) if v is not None)
    if count == 1:
        return
    raise CLIError(
        "Provide exactly one of --person-id, --company-id, --opportunity-id, or --list-entry-id.",
        error_type="usage_error",
        exit_code=2,
    )


@field_value_changes_group.command(name="ls", cls=RichCommand)
@click.option("--field-id", required=True, help="Field id (e.g. field-123).")
@click.option("--person-id", type=int, default=None, help="Filter by person id.")
@click.option("--company-id", type=int, default=None, help="Filter by company id.")
@click.option("--opportunity-id", type=int, default=None, help="Filter by opportunity id.")
@click.option("--list-entry-id", type=int, default=None, help="Filter by list entry id.")
@click.option(
    "--action-type",
    type=click.Choice(["create", "update", "delete"]),
    default=None,
    help="Filter by action type.",
)
@output_options
@click.pass_obj
def field_value_changes_ls(
    ctx: CLIContext,
    *,
    field_id: str,
    person_id: int | None,
    company_id: int | None,
    opportunity_id: int | None,
    list_entry_id: int | None,
    action_type: str | None,
) -> None:
    """List field value changes for a field on a specific entity (V1)."""

    def fn(ctx: CLIContext, warnings: list[str]) -> CommandOutput:
        _validate_exactly_one_selector(person_id, company_id, opportunity_id, list_entry_id)
        client = ctx.get_client(warnings=warnings)
        changes = client.field_value_changes.list(
            field_id=FieldId(field_id),
            person_id=PersonId(person_id) if person_id is not None else None,
            company_id=CompanyId(company_id) if company_id is not None else None,
            opportunity_id=OpportunityId(opportunity_id) if opportunity_id is not None else None,
            list_entry_id=ListEntryId(list_entry_id) if list_entry_id is not None else None,
            action_type=_ACTION_TYPE_MAP[action_type] if action_type else None,
        )
        payload = [_field_value_change_payload(item) for item in changes]
        return CommandOutput(data={"fieldValueChanges": payload}, api_called=True)

    run_command(ctx, command="field-value-changes ls", fn=fn)
