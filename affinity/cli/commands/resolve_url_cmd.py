from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlparse

from affinity.types import CompanyId, ListEntryId, ListId, OpportunityId, PersonId

from ..click_compat import RichCommand, click
from ..context import CLIContext
from ..decorators import category
from ..errors import CLIError
from ..options import output_options
from ..runner import CommandOutput, run_command

ResolvedType = Literal["person", "company", "opportunity", "list", "list_entry"]


@dataclass(frozen=True, slots=True)
class ResolvedUrl:
    type: ResolvedType
    person_id: int | None = None
    company_id: int | None = None
    opportunity_id: int | None = None
    list_id: int | None = None
    list_entry_id: int | None = None


_ENTITY_RE = re.compile(r"^/(persons|companies|opportunities)/(\d+)$")
_LIST_RE = re.compile(r"^/lists/(\d+)$")
_LIST_ENTRY_RE = re.compile(r"^/lists/(\d+)/entries/(\d+)$")


def _parse_affinity_url(url: str) -> ResolvedUrl:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise CLIError(
            "URL must start with http:// or https://", exit_code=2, error_type="usage_error"
        )
    host = (parsed.hostname or "").lower()
    if (
        host not in {"app.affinity.co", "app.affinity.com"}
        and not host.endswith(".affinity.co")
        and not host.endswith(".affinity.com")
    ):
        raise CLIError(
            "Not an Affinity UI URL (expected *.affinity.co or *.affinity.com)",
            exit_code=2,
            error_type="usage_error",
        )

    path = parsed.path.rstrip("/")
    if m := _ENTITY_RE.match(path):
        kind, raw_id = m.group(1), m.group(2)
        entity_id = int(raw_id)
        if kind == "persons":
            return ResolvedUrl(type="person", person_id=entity_id)
        if kind == "companies":
            return ResolvedUrl(type="company", company_id=entity_id)
        return ResolvedUrl(type="opportunity", opportunity_id=entity_id)
    if m := _LIST_ENTRY_RE.match(path):
        return ResolvedUrl(
            type="list_entry",
            list_id=int(m.group(1)),
            list_entry_id=int(m.group(2)),
        )
    if m := _LIST_RE.match(path):
        return ResolvedUrl(type="list", list_id=int(m.group(1)))

    raise CLIError("Unrecognized Affinity URL path.", exit_code=2, error_type="usage_error")


@category("read")
@click.command(name="resolve-url", cls=RichCommand)
@click.argument("url", type=str)
@output_options
@click.pass_obj
def resolve_url_cmd(ctx: CLIContext, url: str) -> None:
    """Resolve an Affinity UI URL to entity type and IDs."""

    def fn(ctx: CLIContext, warnings: list[str]) -> CommandOutput:
        resolved = _parse_affinity_url(url)
        client = ctx.get_client(warnings=warnings)

        # Validate existence/permissions via SDK.
        if resolved.type == "person":
            _ = client.persons.get(PersonId(resolved.person_id or 0))
        elif resolved.type == "company":
            _ = client.companies.get(CompanyId(resolved.company_id or 0))
        elif resolved.type == "opportunity":
            _ = client.opportunities.get(OpportunityId(resolved.opportunity_id or 0))
        elif resolved.type == "list":
            _ = client.lists.get(ListId(resolved.list_id or 0))
        else:
            _ = client.lists.entries(ListId(resolved.list_id or 0)).get(
                ListEntryId(resolved.list_entry_id or 0)
            )

        data = {
            "type": resolved.type,
            "personId": resolved.person_id,
            "companyId": resolved.company_id,
            "opportunityId": resolved.opportunity_id,
            "listId": resolved.list_id,
            "listEntryId": resolved.list_entry_id,
            "canonicalUrl": _canonical_url(resolved),
        }
        return CommandOutput(
            data={k: v for k, v in data.items() if v is not None},
            warnings=warnings,
            api_called=True,
        )

    run_command(ctx, command="resolve-url", fn=fn)


def _canonical_url(resolved: ResolvedUrl) -> str:
    if resolved.type == "person":
        return f"https://app.affinity.co/persons/{resolved.person_id}"
    if resolved.type == "company":
        return f"https://app.affinity.co/companies/{resolved.company_id}"
    if resolved.type == "opportunity":
        return f"https://app.affinity.co/opportunities/{resolved.opportunity_id}"
    if resolved.type == "list":
        return f"https://app.affinity.co/lists/{resolved.list_id}"
    return f"https://app.affinity.co/lists/{resolved.list_id}/entries/{resolved.list_entry_id}"
