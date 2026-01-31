from __future__ import annotations

import platform

import affinity

from ..click_compat import RichCommand, click
from ..context import CLIContext
from ..decorators import category
from ..options import output_options
from ..runner import CommandOutput, run_command


@category("local")
@click.command(name="version", cls=RichCommand)
@output_options
@click.pass_obj
def version_cmd(ctx: CLIContext) -> None:
    """Show version, Python, and platform information."""

    def fn(ctx: CLIContext, _warnings: list[str]) -> CommandOutput:
        data: dict[str, object] = {
            "version": affinity.__version__,
            "pythonVersion": platform.python_version(),
            "platform": platform.platform(),
        }

        # Include cached update info if available
        try:
            from ..update_check import get_cached_update_info

            cache_path = ctx.paths.state_dir / "update_check.json"
            cached = get_cached_update_info(cache_path)
            if cached is not None:
                data["update"] = {
                    "available": cached.update_available,
                    "latestVersion": cached.latest_version,
                    "checkedAt": cached.checked_at.isoformat(),
                }
            else:
                data["update"] = None
        except Exception:
            # Don't fail version command if update check fails
            data["update"] = None

        return CommandOutput(data=data, api_called=False)

    run_command(ctx, command="version", fn=fn)
