from __future__ import annotations

from affinity.models.secondary import RelationshipStrength
from affinity.types import PersonId, UserId

from ..click_compat import RichCommand, RichGroup, click
from ..context import CLIContext
from ..options import output_options
from ..runner import CommandOutput, run_command


@click.group(name="relationship-strength", cls=RichGroup)
def relationship_strength_group() -> None:
    """Relationship strength commands."""


def _strength_payload(item: RelationshipStrength) -> dict[str, object]:
    return item.model_dump(by_alias=True, mode="json", exclude_none=True)


@relationship_strength_group.command(name="get", cls=RichCommand)
@click.option("--external-id", type=int, required=True, help="External person id.")
@click.option("--internal-id", type=int, default=None, help="Internal user id.")
@output_options
@click.pass_obj
def relationship_strength_get(
    ctx: CLIContext,
    *,
    external_id: int,
    internal_id: int | None,
) -> None:
    """Get relationship strengths (V1)."""

    def fn(ctx: CLIContext, warnings: list[str]) -> CommandOutput:
        client = ctx.get_client(warnings=warnings)
        strengths = client.relationships.get(
            external_id=PersonId(external_id),
            internal_id=UserId(internal_id) if internal_id is not None else None,
        )
        payload = [_strength_payload(item) for item in strengths]
        return CommandOutput(data={"relationshipStrengths": payload}, api_called=True)

    run_command(ctx, command="relationship-strength get", fn=fn)
