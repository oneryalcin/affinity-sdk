"""Session cache management commands."""

from __future__ import annotations

import os
import shutil
import tempfile
import time
from pathlib import Path

from ..click_compat import RichCommand, RichGroup, click
from ..decorators import category


@click.group(name="session", cls=RichGroup)
def session_group() -> None:
    """Manage CLI session cache for pipeline optimization."""


@category("local")
@session_group.command(name="start", cls=RichCommand)
def session_start() -> None:
    """Create a new session cache directory.

    Usage: export AFFINITY_SESSION_CACHE=$(affinity session start)
    """
    try:
        cache_dir = tempfile.mkdtemp(prefix="affinity_session_")
        # Output just the path (no newline issues with click.echo)
        click.echo(cache_dir)
    except OSError as e:
        click.echo(f"Error: Cannot create session cache: {e}", err=True)
        raise SystemExit(1) from None


@category("local")
@session_group.command(name="end", cls=RichCommand)
def session_end() -> None:
    """Clean up the current session cache.

    Reads AFFINITY_SESSION_CACHE env var and removes the directory.
    Safe to call multiple times (idempotent).
    """
    cache_dir = os.environ.get("AFFINITY_SESSION_CACHE")
    if not cache_dir:
        click.echo("No active session (AFFINITY_SESSION_CACHE not set)", err=True)
        return
    cache_path = Path(cache_dir)
    if cache_path.exists():
        shutil.rmtree(cache_dir, ignore_errors=True)
        click.echo(f"Session ended: {cache_dir}", err=True)
    else:
        click.echo(f"Session directory already removed: {cache_dir}", err=True)


@category("local")
@session_group.command(name="status", cls=RichCommand)
def session_status() -> None:
    """Show current session cache status.

    Note: Shows stats for ALL cache files in the directory, regardless of
    which API key created them. Filtering by tenant would require API key
    access, which this command intentionally avoids.
    """
    cache_dir = os.environ.get("AFFINITY_SESSION_CACHE")
    if not cache_dir:
        click.echo("No active session (AFFINITY_SESSION_CACHE not set)")
        return

    cache_path = Path(cache_dir)
    if not cache_path.exists():
        click.echo(f"Session directory missing: {cache_dir}")
        return

    # Count cache entries and calculate stats
    cache_files = list(cache_path.glob("*.json"))
    total_size = sum(f.stat().st_size for f in cache_files)
    oldest_mtime = min((f.stat().st_mtime for f in cache_files), default=time.time())
    age_seconds = int(time.time() - oldest_mtime)

    click.echo(f"Session active: {cache_dir}")
    click.echo(f"Cache entries: {len(cache_files)}")
    click.echo(f"Total size: {total_size / 1024:.1f} KB")
    click.echo(f"Oldest entry: {age_seconds // 60}m {age_seconds % 60}s ago")
