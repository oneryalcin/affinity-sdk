from __future__ import annotations

from affinity.models.entities import FieldValue, FieldValueCreate
from affinity.types import CompanyId, FieldId, FieldValueId, ListEntryId, OpportunityId, PersonId

from ..click_compat import RichCommand, RichGroup, click
from ..context import CLIContext
from ..errors import CLIError
from ..options import output_options
from ..runner import CommandOutput, run_command
from ..serialization import serialize_model_for_cli
from ._v1_parsing import parse_json_value


@click.group(name="field-value", cls=RichGroup)
def field_value_group() -> None:
    """Field value commands."""


def _field_value_payload(value: FieldValue) -> dict[str, object]:
    return serialize_model_for_cli(value)


def _validate_exactly_one_target(
    person_id: int | None,
    company_id: int | None,
    opportunity_id: int | None,
    list_entry_id: int | None,
) -> None:
    count = sum(
        1 for value in (person_id, company_id, opportunity_id, list_entry_id) if value is not None
    )
    if count == 1:
        return
    raise CLIError(
        "Provide exactly one of --person-id, --company-id, --opportunity-id, or --list-entry-id.",
        error_type="usage_error",
        exit_code=2,
    )


@field_value_group.command(name="ls", cls=RichCommand)
@click.option("--person-id", type=int, default=None, help="Filter by person id.")
@click.option("--company-id", type=int, default=None, help="Filter by company id.")
@click.option("--opportunity-id", type=int, default=None, help="Filter by opportunity id.")
@click.option("--list-entry-id", type=int, default=None, help="Filter by list entry id.")
@output_options
@click.pass_obj
def field_value_ls(
    ctx: CLIContext,
    *,
    person_id: int | None,
    company_id: int | None,
    opportunity_id: int | None,
    list_entry_id: int | None,
) -> None:
    """
    List field values for a single entity.

    Provide exactly one of --person-id, --company-id, --opportunity-id, or --list-entry-id.

    Examples:

    - `affinity field-value ls --person-id 12345`
    - `affinity field-value ls --company-id 67890`
    """

    def fn(ctx: CLIContext, warnings: list[str]) -> CommandOutput:
        _validate_exactly_one_target(person_id, company_id, opportunity_id, list_entry_id)
        client = ctx.get_client(warnings=warnings)
        values = client.field_values.list(
            person_id=PersonId(person_id) if person_id is not None else None,
            company_id=CompanyId(company_id) if company_id is not None else None,
            opportunity_id=OpportunityId(opportunity_id) if opportunity_id is not None else None,
            list_entry_id=ListEntryId(list_entry_id) if list_entry_id is not None else None,
        )
        payload = [_field_value_payload(value) for value in values]
        return CommandOutput(data={"fieldValues": payload}, api_called=True)

    run_command(ctx, command="field-value ls", fn=fn)


@field_value_group.command(name="create", cls=RichCommand)
@click.option("--field-id", required=True, help="Field id (e.g. field-123).")
@click.option("--entity-id", required=True, type=int, help="Entity id for the value.")
@click.option("--value", default=None, help="Field value (string).")
@click.option("--value-json", default=None, help="Field value (JSON literal).")
@click.option("--list-entry-id", type=int, default=None, help="Optional list entry id.")
@output_options
@click.pass_obj
def field_value_create(
    ctx: CLIContext,
    *,
    field_id: str,
    entity_id: int,
    value: str | None,
    value_json: str | None,
    list_entry_id: int | None,
) -> None:
    """
    Create a field value on an entity.

    Examples:

    - `affinity field-value create --field-id field-123 --entity-id 456 --value "Active"`
    - `affinity field-value create --field-id field-789 --entity-id 456 --value-json '[1,2,3]'`
    """

    def fn(ctx: CLIContext, warnings: list[str]) -> CommandOutput:
        if value is None and value_json is None:
            raise CLIError(
                "Provide --value or --value-json.",
                error_type="usage_error",
                exit_code=2,
            )
        if value is not None and value_json is not None:
            raise CLIError(
                "Use only one of --value or --value-json.",
                error_type="usage_error",
                exit_code=2,
            )
        parsed_value = value if value_json is None else parse_json_value(value_json, label="value")
        client = ctx.get_client(warnings=warnings)
        created = client.field_values.create(
            FieldValueCreate(
                field_id=FieldId(field_id),
                entity_id=entity_id,
                value=parsed_value,
                list_entry_id=ListEntryId(list_entry_id) if list_entry_id is not None else None,
            )
        )
        payload = _field_value_payload(created)
        return CommandOutput(data={"fieldValue": payload}, api_called=True)

    run_command(ctx, command="field-value create", fn=fn)


@field_value_group.command(name="update", cls=RichCommand)
@click.argument("field_value_id", type=int)
@click.option("--value", default=None, help="Field value (string).")
@click.option("--value-json", default=None, help="Field value (JSON literal).")
@output_options
@click.pass_obj
def field_value_update(
    ctx: CLIContext,
    field_value_id: int,
    *,
    value: str | None,
    value_json: str | None,
) -> None:
    """Update a field value (V1 write path)."""

    def fn(ctx: CLIContext, warnings: list[str]) -> CommandOutput:
        if value is None and value_json is None:
            raise CLIError(
                "Provide --value or --value-json.",
                error_type="usage_error",
                exit_code=2,
            )
        if value is not None and value_json is not None:
            raise CLIError(
                "Use only one of --value or --value-json.",
                error_type="usage_error",
                exit_code=2,
            )
        parsed_value = value if value_json is None else parse_json_value(value_json, label="value")
        client = ctx.get_client(warnings=warnings)
        updated = client.field_values.update(FieldValueId(field_value_id), parsed_value)
        payload = _field_value_payload(updated)
        return CommandOutput(data={"fieldValue": payload}, api_called=True)

    run_command(ctx, command="field-value update", fn=fn)


@field_value_group.command(name="delete", cls=RichCommand)
@click.argument("field_value_id", type=int)
@output_options
@click.pass_obj
def field_value_delete(ctx: CLIContext, field_value_id: int) -> None:
    """Delete a field value (V1 write path)."""

    def fn(ctx: CLIContext, warnings: list[str]) -> CommandOutput:
        client = ctx.get_client(warnings=warnings)
        success = client.field_values.delete(FieldValueId(field_value_id))
        return CommandOutput(data={"success": success}, api_called=True)

    run_command(ctx, command="field-value delete", fn=fn)
