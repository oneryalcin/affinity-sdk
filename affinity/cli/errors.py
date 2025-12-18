from __future__ import annotations

from typing import Any


class CLIError(Exception):
    def __init__(
        self,
        message: str,
        *,
        exit_code: int = 1,
        error_type: str = "error",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.exit_code = exit_code
        self.error_type = error_type
        self.details = details

    def __str__(self) -> str:  # pragma: no cover
        return self.message
