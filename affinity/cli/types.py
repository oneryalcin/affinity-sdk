"""Type definitions for CLI components."""

from __future__ import annotations

from typing import Any, Protocol

# Type alias for JSON-serializable values
# This is a recursive type definition - JsonValue can contain itself
JsonValue = str | int | float | bool | None | dict[str, "JsonValue"] | list["JsonValue"]
JsonDict = dict[str, JsonValue]


def validate_json_serializable(data: Any, path: str = "root") -> None:
    """
    Validate that data contains only JSON-serializable types.

    This function recursively traverses the data structure and ensures
    all values are JSON-safe (str, int, float, bool, None, dict, or list).
    Non-JSON-safe types like datetime, UUID, or Pydantic models will raise
    TypeError.

    Args:
        data: The data structure to validate
        path: Current path in the data structure (for error messages)

    Raises:
        TypeError: If non-JSON-safe types are found

    Example:
        >>> validate_json_serializable({"id": 123, "name": "John"})
        # No error - all types are JSON-safe

        >>> from datetime import datetime
        >>> validate_json_serializable({"created": datetime.now()})
        Traceback (most recent call last):
            ...
        TypeError: Non-JSON-serializable type at root.created: datetime
    """
    if isinstance(data, dict):
        for key, value in data.items():
            validate_json_serializable(value, f"{path}.{key}")
    elif isinstance(data, list):
        for i, item in enumerate(data):
            validate_json_serializable(item, f"{path}[{i}]")
    elif isinstance(data, (str, int, float, bool, type(None))):
        # These are JSON-safe primitive types
        pass
    else:
        raise TypeError(
            f"Non-JSON-serializable type at {path}: {type(data).__name__} (value: {data!r})"
        )


class CommandOutputProtocol(Protocol):
    """
    Protocol for command output validation.

    This defines the expected interface for CLI command outputs,
    ensuring they contain only JSON-serializable data.
    """

    @property
    def data(self) -> JsonDict | None:
        """Output data (must be JSON-serializable)."""
        ...

    @property
    def api_called(self) -> bool:
        """Whether an API call was made."""
        ...
