from __future__ import annotations

from affinity.models.entities import FieldCreate, FieldMetadata
from affinity.models.types import EntityType, FieldValueType
from affinity.types import FieldId, ListId

from ..click_compat import RichCommand, RichGroup, click
from ..context import CLIContext
from ..errors import CLIError
from ..options import output_options
from ..runner import CommandOutput, run_command
from ._v1_parsing import parse_choice


@click.group(name="field", cls=RichGroup)
def field_group() -> None:
    """Field commands."""


_ENTITY_TYPE_MAP = {
    "person": EntityType.PERSON,
    "people": EntityType.PERSON,
    "company": EntityType.ORGANIZATION,
    "organization": EntityType.ORGANIZATION,
    "opportunity": EntityType.OPPORTUNITY,
}

_VALUE_TYPE_MAP = {ft.value: ft for ft in FieldValueType}


def _field_payload(field: FieldMetadata) -> dict[str, object]:
    return field.model_dump(by_alias=True, exclude_none=True)


@field_group.command(name="ls", cls=RichCommand)
@click.option("--list-id", type=int, default=None, help="Filter by list id.")
@click.option(
    "--entity-type",
    type=click.Choice(sorted(_ENTITY_TYPE_MAP.keys())),
    default=None,
    help="Filter by entity type (person/company/opportunity).",
)
@output_options
@click.pass_obj
def field_ls(
    ctx: CLIContext,
    *,
    list_id: int | None,
    entity_type: str | None,
) -> None:
    """List fields (V1)."""

    def fn(ctx: CLIContext, warnings: list[str]) -> CommandOutput:
        client = ctx.get_client(warnings=warnings)
        parsed_type = parse_choice(entity_type, _ENTITY_TYPE_MAP, label="entity type")
        fields = client.fields.list(
            list_id=ListId(list_id) if list_id is not None else None,
            entity_type=parsed_type,
        )
        payload = [_field_payload(field) for field in fields]
        return CommandOutput(data={"fields": payload}, api_called=True)

    run_command(ctx, command="field ls", fn=fn)


@field_group.command(name="create", cls=RichCommand)
@click.option("--name", required=True, help="Field name.")
@click.option(
    "--entity-type",
    type=click.Choice(sorted(_ENTITY_TYPE_MAP.keys())),
    required=True,
    help="Entity type (person/company/opportunity).",
)
@click.option(
    "--value-type",
    type=click.Choice(sorted(_VALUE_TYPE_MAP.keys())),
    required=True,
    help="Field value type (e.g. text, dropdown, person, number).",
)
@click.option("--list-id", type=int, default=None, help="List id for list-specific field.")
@click.option("--allows-multiple", is_flag=True, help="Allow multiple values.")
@click.option("--list-specific", is_flag=True, help="Mark as list-specific.")
@click.option("--required", is_flag=True, help="Mark as required.")
@output_options
@click.pass_obj
def field_create(
    ctx: CLIContext,
    *,
    name: str,
    entity_type: str,
    value_type: str,
    list_id: int | None,
    allows_multiple: bool,
    list_specific: bool,
    required: bool,
) -> None:
    """Create a field (V1 write path)."""

    def fn(ctx: CLIContext, warnings: list[str]) -> CommandOutput:
        parsed_entity_type = parse_choice(entity_type, _ENTITY_TYPE_MAP, label="entity type")
        parsed_value_type = parse_choice(value_type, _VALUE_TYPE_MAP, label="value type")
        if parsed_entity_type is None or parsed_value_type is None:
            raise CLIError("Missing required field options.", error_type="usage_error", exit_code=2)
        client = ctx.get_client(warnings=warnings)
        created = client.fields.create(
            FieldCreate(
                name=name,
                entity_type=parsed_entity_type,
                value_type=parsed_value_type,
                list_id=ListId(list_id) if list_id is not None else None,
                allows_multiple=allows_multiple,
                is_list_specific=list_specific,
                is_required=required,
            )
        )
        payload = _field_payload(created)
        return CommandOutput(data={"field": payload}, api_called=True)

    run_command(ctx, command="field create", fn=fn)


@field_group.command(name="delete", cls=RichCommand)
@click.argument("field_id")
@output_options
@click.pass_obj
def field_delete(ctx: CLIContext, field_id: str) -> None:
    """Delete a field (V1 write path)."""

    def fn(ctx: CLIContext, warnings: list[str]) -> CommandOutput:
        client = ctx.get_client(warnings=warnings)
        success = client.fields.delete(FieldId(field_id))
        return CommandOutput(data={"success": success}, api_called=True)

    run_command(ctx, command="field delete", fn=fn)
