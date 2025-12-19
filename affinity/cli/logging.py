from __future__ import annotations

import logging
from contextlib import suppress
from dataclasses import dataclass
from logging.handlers import RotatingFileHandler
from pathlib import Path


class _RedactFilter(logging.Filter):
    def __init__(self, *, api_key: str | None):
        super().__init__()
        self._api_key = api_key

    def set_api_key(self, api_key: str | None) -> None:
        self._api_key = api_key

    def filter(self, record: logging.LogRecord) -> bool:
        if self._api_key:
            record.msg = str(record.getMessage()).replace(self._api_key, "[REDACTED]")
            record.args = ()
        return True


@dataclass(frozen=True)
class LoggingState:
    handlers: list[logging.Handler]
    level: int


def configure_logging(
    *,
    verbosity: int,
    log_file: Path | None,
    enable_file: bool,
    api_key_for_redaction: str | None,
) -> LoggingState:
    level = logging.WARNING
    if verbosity >= 2:
        level = logging.DEBUG
    elif verbosity == 1:
        level = logging.INFO

    root = logging.getLogger()
    previous = LoggingState(handlers=list(root.handlers), level=root.level)
    root.setLevel(level)

    # Avoid duplicate handlers when invoked multiple times (tests).
    for h in list(root.handlers):
        root.removeHandler(h)
        with suppress(Exception):
            h.close()

    stderr_handler = logging.StreamHandler()
    stderr_handler.setLevel(level)
    stderr_handler.addFilter(_RedactFilter(api_key=api_key_for_redaction))
    stderr_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    root.addHandler(stderr_handler)

    if enable_file and log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=2_000_000,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.INFO if verbosity < 2 else logging.DEBUG)
        file_handler.addFilter(_RedactFilter(api_key=api_key_for_redaction))
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        )
        root.addHandler(file_handler)

    return previous


def restore_logging(state: LoggingState) -> None:
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
        with suppress(Exception):
            h.close()
    for h in state.handlers:
        root.addHandler(h)
    root.setLevel(state.level)


def set_redaction_api_key(api_key: str | None) -> None:
    """
    Update any CLI-installed redaction filters with the resolved API key.

    This avoids resolving credentials eagerly at process start (so no-network commands
    stay no-network), while still providing defense-in-depth once credentials exist.
    """
    root = logging.getLogger()
    for handler in root.handlers:
        for flt in handler.filters:
            if isinstance(flt, _RedactFilter):
                flt.set_api_key(api_key)
