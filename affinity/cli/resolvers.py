"""
Standard resolver types for CLI commands.

These dataclasses provide consistent structure for resolved metadata,
ensuring all CLI commands follow the same patterns when resolving
user inputs (IDs, URLs, emails, names, etc.) to API parameters.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal


@dataclass(frozen=True, slots=True)
class ResolvedEntity:
    """
    Standard structure for entity resolution metadata.

    This class represents how a user's input selector (ID, URL, email, name)
    was resolved to an entity ID for API calls.

    Attributes:
        input: The original user input (e.g., "john@example.com", "123", "acme.com")
        entity_id: The resolved numeric entity ID
        entity_type: Type of entity (person, company, opportunity, list)
        source: How the input was resolved (id, url, email, name, domain)
        canonical_url: Optional canonical Affinity URL for the entity

    Example:
        >>> resolved = ResolvedEntity(
        ...     input="john@example.com",
        ...     entity_id=12345,
        ...     entity_type="person",
        ...     source="email",
        ...     canonical_url="https://app.affinity.co/persons/12345"
        ... )
        >>> resolved.to_dict()
        {
            'input': 'john@example.com',
            'personId': 12345,
            'source': 'email',
            'canonicalUrl': 'https://app.affinity.co/persons/12345'
        }
    """

    input: str
    entity_id: int
    entity_type: Literal["person", "company", "opportunity", "list"]
    source: Literal["id", "url", "email", "name", "domain"]
    canonical_url: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """
        Convert to dict for resolved metadata.

        Returns a dictionary suitable for inclusion in CommandOutput.resolved,
        with entity_id renamed to {entityType}Id (e.g., personId, companyId).
        """
        data = asdict(self)
        # Rename entity_id to {entityType}Id
        entity_id = data.pop("entity_id")
        data[f"{self.entity_type}Id"] = entity_id
        # Remove entity_type from output (it's redundant with the key name)
        data.pop("entity_type", None)
        # Convert snake_case to camelCase for canonical_url
        if "canonical_url" in data and data["canonical_url"] is not None:
            data["canonicalUrl"] = data.pop("canonical_url")
        elif "canonical_url" in data:
            data.pop("canonical_url")
        return data


@dataclass(frozen=True, slots=True)
class ResolvedFieldSelection:
    """
    Field selection resolution metadata.

    This class represents which fields were requested by the user
    through --field-id or --field-type flags.

    Attributes:
        field_ids: List of specific field IDs requested (e.g., ["field-123", "field-456"])
        field_types: List of field types requested (e.g., ["global", "enriched"])

    Example:
        >>> resolved = ResolvedFieldSelection(
        ...     field_ids=["field-123"],
        ...     field_types=["global", "enriched"]
        ... )
        >>> resolved.to_dict()
        {'fieldIds': ['field-123'], 'fieldTypes': ['global', 'enriched']}
    """

    field_ids: list[str] | None = None
    field_types: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        """
        Convert to dict, excluding None values.

        Returns a dictionary with camelCase field names, omitting any
        fields that are None.
        """
        result = {}
        if self.field_ids is not None:
            result["fieldIds"] = self.field_ids
        if self.field_types is not None:
            result["fieldTypes"] = self.field_types
        return result


@dataclass(frozen=True, slots=True)
class ResolvedList:
    """
    List resolution metadata.

    This class represents how a user's list selector (ID, URL, name)
    was resolved to a list ID.

    Attributes:
        input: The original user input
        list_id: The resolved numeric list ID
        source: How the input was resolved (id, url, name)

    Example:
        >>> resolved = ResolvedList(
        ...     input="Sales Pipeline",
        ...     list_id=789,
        ...     source="name"
        ... )
        >>> resolved.to_dict()
        {'input': 'Sales Pipeline', 'listId': 789, 'source': 'name'}
    """

    input: str
    list_id: int
    source: Literal["id", "url", "name"]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict with camelCase field names."""
        return {
            "input": self.input,
            "listId": self.list_id,
            "source": self.source,
        }


@dataclass(frozen=True, slots=True)
class ResolvedSavedView:
    """
    Saved view resolution metadata.

    This class represents how a user's saved view selector was resolved
    to a saved view ID.

    Attributes:
        input: The original user input
        saved_view_id: The resolved numeric saved view ID
        name: The name of the saved view

    Example:
        >>> resolved = ResolvedSavedView(
        ...     input="Active Deals",
        ...     saved_view_id=456,
        ...     name="Active Deals"
        ... )
        >>> resolved.to_dict()
        {'input': 'Active Deals', 'savedViewId': 456, 'name': 'Active Deals'}
    """

    input: str
    saved_view_id: int
    name: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict with camelCase field names."""
        return {
            "input": self.input,
            "savedViewId": self.saved_view_id,
            "name": self.name,
        }


def build_resolved_metadata(
    *,
    entity: ResolvedEntity | None = None,
    list_resolution: ResolvedList | None = None,
    saved_view: ResolvedSavedView | None = None,
    field_selection: ResolvedFieldSelection | None = None,
    expand: list[str] | None = None,
) -> dict[str, Any]:
    """
    Build a complete resolved metadata dict for CommandOutput.

    This is a convenience function to construct the resolved metadata
    dictionary in a consistent way across all commands.

    Args:
        entity: Entity resolution metadata (person, company, opportunity)
        list_resolution: List resolution metadata
        saved_view: Saved view resolution metadata
        field_selection: Field selection metadata
        expand: List of expansion options used

    Returns:
        Dictionary suitable for CommandOutput(resolved=...)

    Example:
        >>> person = ResolvedEntity(
        ...     input="john@example.com",
        ...     entity_id=12345,
        ...     entity_type="person",
        ...     source="email"
        ... )
        >>> fields = ResolvedFieldSelection(field_types=["global"])
        >>> resolved = build_resolved_metadata(
        ...     entity=person,
        ...     field_selection=fields,
        ...     expand=["lists"]
        ... )
        >>> resolved
        {
            'person': {'input': 'john@example.com', 'personId': 12345, 'source': 'email'},
            'fieldSelection': {'fieldTypes': ['global']},
            'expand': ['lists']
        }
    """
    result: dict[str, Any] = {}

    if entity is not None:
        # Use entity_type as the key (e.g., "person", "company")
        result[entity.entity_type] = entity.to_dict()

    if list_resolution is not None:
        result["list"] = list_resolution.to_dict()

    if saved_view is not None:
        result["savedView"] = saved_view.to_dict()

    if field_selection is not None:
        field_dict = field_selection.to_dict()
        if field_dict:  # Only include if not empty
            result["fieldSelection"] = field_dict

    if expand is not None and expand:
        result["expand"] = expand

    return result
