"""
Standard serialization patterns for CLI commands.

All CLI commands should use these helpers to ensure consistent JSON output.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel


def serialize_model_for_cli(model: BaseModel) -> dict[str, Any]:
    """
    Serialize a Pydantic model for CLI JSON output.

    This is the standard serialization pattern for all CLI commands.
    It ensures:
    1. JSON-safe types (datetime → ISO string, etc.)
    2. Consistent null handling (None values excluded)
    3. Field aliases used (camelCase for API compatibility)

    Args:
        model: Any Pydantic model to serialize

    Returns:
        Dictionary suitable for JSON output

    Example:
        >>> from affinity.models.entities import Person
        >>> person = Person(id=123, first_name="John", last_name="Doe", emails=[])
        >>> result = serialize_model_for_cli(person)
        >>> result['id']
        123
        >>> result['firstName']
        'John'
    """
    return model.model_dump(by_alias=True, mode="json", exclude_none=True)


def serialize_models_for_cli(models: Sequence[BaseModel]) -> list[dict[str, Any]]:
    """
    Serialize a sequence of Pydantic models for CLI JSON output.

    Args:
        models: Sequence of Pydantic models

    Returns:
        List of dictionaries suitable for JSON output

    Example:
        >>> from affinity.models.entities import Person
        >>> people = [
        ...     Person(id=1, first_name="Alice", last_name="Smith", emails=[]),
        ...     Person(id=2, first_name="Bob", last_name="Jones", emails=[])
        ... ]
        >>> results = serialize_models_for_cli(people)
        >>> len(results)
        2
        >>> results[0]['firstName']
        'Alice'
    """
    return [serialize_model_for_cli(model) for model in models]
