from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import unquote_to_bytes


@dataclass(frozen=True)
class DownloadedFile:
    """
    A streamed download response with useful metadata extracted from headers.

    Notes:
    - `filename` is derived from `Content-Disposition` when present.
    - `size` is derived from `Content-Length` when present.
    - `headers` is a lossy dict view (last value wins); use `raw_headers` when needed.
    """

    headers: dict[str, str]
    raw_headers: list[tuple[str, str]]
    content_type: str | None
    filename: str | None
    size: int | None
    iter_bytes: Iterator[bytes]


@dataclass(frozen=True)
class AsyncDownloadedFile:
    """
    Async variant of `DownloadedFile`.
    """

    headers: dict[str, str]
    raw_headers: list[tuple[str, str]]
    content_type: str | None
    filename: str | None
    size: int | None
    iter_bytes: AsyncIterator[bytes]


def _filename_from_content_disposition(value: str | None) -> str | None:
    if not value:
        return None

    # Common shapes:
    # - attachment; filename="file.txt"
    # - attachment; filename=file.txt
    # - attachment; filename*=UTF-8''file%20name.txt
    parts = [p.strip() for p in value.split(";") if p.strip()]
    if len(parts) <= 1:
        return None

    params: dict[str, str] = {}
    for part in parts[1:]:
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        key = k.strip().lower()
        raw = v.strip()
        if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in {'"', "'"}:
            raw = raw[1:-1]
        params[key] = raw

    filename: str | None = None
    if "filename*" in params:
        raw = params["filename*"]
        try:
            charset = "utf-8"
            encoded = raw
            if "''" in raw:
                charset, encoded = raw.split("''", 1)
            elif "'" in raw:
                # charset'lang'value
                charset, rest = raw.split("'", 1)
                _, encoded = rest.split("'", 1)
            decoded_bytes = unquote_to_bytes(encoded)
            filename = decoded_bytes.decode(charset or "utf-8", errors="replace")
        except Exception:
            filename = None

    if filename is None and "filename" in params:
        filename = params["filename"]

    if not filename:
        return None

    # Avoid returning path-like values.
    safe = Path(filename).name
    return safe or None


def _download_info_from_headers(
    raw_headers: list[tuple[str, str]],
) -> dict[str, Any]:
    headers = dict(raw_headers)
    content_type = headers.get("Content-Type") or headers.get("content-type")
    content_disposition = headers.get("Content-Disposition") or headers.get("content-disposition")
    length = headers.get("Content-Length") or headers.get("content-length")

    size: int | None = None
    if length is not None:
        try:
            size = int(length)
        except Exception:
            size = None

    return {
        "headers": headers,
        "content_type": content_type,
        "filename": _filename_from_content_disposition(content_disposition),
        "size": size,
    }
