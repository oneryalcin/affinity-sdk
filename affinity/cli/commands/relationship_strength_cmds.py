from __future__ import annotations

from affinity.models.secondary import RelationshipStrength
from affinity.types import PersonId, UserId

from ..click_compat import RichCommand, RichGroup, click
from ..context import CLIContext
from ..decorators import category
from ..options import output_options
from ..results import CommandContext
from ..runner import CommandOutput, run_command
from ..serialization import serialize_model_for_cli


@click.group(name="relationship-strength", cls=RichGroup)
def relationship_strength_group() -> None:
    """Relationship strength commands."""


def _strength_payload(item: RelationshipStrength) -> dict[str, object]:
    return serialize_model_for_cli(item)


@category("read")
@relationship_strength_group.command(name="ls", cls=RichCommand)
@click.option("--external-id", type=int, required=True, help="External person id.")
@click.option("--internal-id", type=int, default=None, help="Internal user id.")
@output_options
@click.pass_obj
def relationship_strength_ls(
    ctx: CLIContext,
    *,
    external_id: int,
    internal_id: int | None,
) -> None:
    """List relationship strengths."""

    def fn(ctx: CLIContext, warnings: list[str]) -> CommandOutput:
        client = ctx.get_client(warnings=warnings)
        strengths = client.relationships.get(
            external_id=PersonId(external_id),
            internal_id=UserId(internal_id) if internal_id is not None else None,
        )
        payload = [_strength_payload(item) for item in strengths]

        # Build CommandContext
        # Both externalId and internalId are inputs (composite key per spec)
        ctx_inputs: dict[str, object] = {"externalId": external_id}
        if internal_id is not None:
            ctx_inputs["internalId"] = internal_id

        cmd_context = CommandContext(
            name="relationship-strength ls",
            inputs=ctx_inputs,
            modifiers={},
        )

        return CommandOutput(
            data={"relationshipStrengths": payload}, context=cmd_context, api_called=True
        )

    run_command(ctx, command="relationship-strength ls", fn=fn)
