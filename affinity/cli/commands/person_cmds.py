from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TypedDict

from affinity import AsyncAffinity
from affinity.models.entities import Person
from affinity.models.rate_limit_snapshot import RateLimitSnapshot
from affinity.models.secondary import EntityFile
from affinity.models.types import V1_BASE_URL, V2_BASE_URL
from affinity.types import PersonId

from ..click_compat import RichCommand, RichGroup, click
from ..context import CLIContext
from ..csv_utils import sanitize_filename
from ..options import output_options
from ..progress import ProgressManager, ProgressSettings
from ..runner import CommandOutput, run_command


@click.group(name="person", cls=RichGroup)
def person_group() -> None:
    """Person commands."""


@person_group.command(name="search", cls=RichCommand)
@click.argument("query")
@click.option("--page-size", type=int, default=None, help="v1 page size (max 500).")
@click.option("--page-token", type=str, default=None, help="v1 page token for resuming.")
@click.option("--max-results", type=int, default=None, help="Stop after N results total.")
@click.option("--all", "all_pages", is_flag=True, help="Fetch all pages.")
@output_options
@click.pass_obj
def person_search(
    ctx: CLIContext,
    query: str,
    *,
    page_size: int | None,
    page_token: str | None,
    max_results: int | None,
    all_pages: bool,
) -> None:
    def fn(ctx: CLIContext, warnings: list[str]) -> CommandOutput:
        client = ctx.get_client(warnings=warnings)
        results: list[dict[str, object]] = []
        next_token = page_token

        fetched_first_page = False
        while True:
            resp = client.persons.search(
                query,
                with_interaction_dates=True,
                page_size=page_size,
                page_token=next_token,
            )
            fetched_first_page = True
            for person in resp.data:
                results.append(_person_row(person))
                if max_results is not None and len(results) >= max_results:
                    return CommandOutput(
                        data=results[:max_results],
                        pagination={"nextPageToken": resp.next_page_token},
                        api_called=True,
                    )

            if not resp.next_page_token:
                return CommandOutput(data=results, pagination=None, api_called=True)

            if not all_pages and fetched_first_page and max_results is None:
                return CommandOutput(
                    data=results,
                    pagination={"nextPageToken": resp.next_page_token},
                    api_called=True,
                )

            next_token = resp.next_page_token

    run_command(ctx, command="person search", fn=fn)


def _person_row(person: Person) -> dict[str, object]:
    last_interaction = None
    if person.interaction_dates is not None:
        last_interaction = person.interaction_dates.last_interaction_date
    return {
        "id": int(person.id),
        "name": person.full_name,
        "primaryEmail": person.primary_email,
        "emails": person.emails,
        "lastInteractionDate": last_interaction,
    }


@person_group.group(name="files", cls=RichGroup)
def person_files_group() -> None:
    """Person files."""


@person_files_group.command(name="dump", cls=RichCommand)
@click.argument("person_id", type=int)
@click.option("--out", "out_dir", type=click.Path(), default=None)
@click.option("--overwrite", is_flag=True, help="Overwrite existing files.")
@click.option("--concurrency", type=int, default=3, show_default=True)
@click.option("--page-size", type=int, default=200, show_default=True)
@click.option("--max-files", type=int, default=None, help="Stop after N files.")
@output_options
@click.pass_obj
def person_files_dump(
    ctx: CLIContext,
    person_id: int,
    *,
    out_dir: str | None,
    overwrite: bool,
    concurrency: int,
    page_size: int,
    max_files: int | None,
) -> None:
    def fn(ctx: CLIContext, warnings: list[str]) -> CommandOutput:
        # Use AsyncAffinity for safe concurrency.
        ctx.load_dotenv_if_requested()
        api_key = ctx.resolve_api_key(warnings=warnings)

        entity_dir = (
            Path(out_dir)
            if out_dir is not None
            else Path.cwd() / f"affinity-person-{person_id}-files"
        )
        files_dir = entity_dir / "files"
        files_dir.mkdir(parents=True, exist_ok=True)

        rate_limit_snapshot: RateLimitSnapshot | None = None

        async def run() -> dict[str, object]:
            async with AsyncAffinity(
                api_key=api_key,
                v1_base_url=ctx.v1_base_url or V1_BASE_URL,
                v2_base_url=ctx.v2_base_url or V2_BASE_URL,
                timeout=ctx.timeout or 30.0,
                log_requests=ctx.verbosity >= 2,
            ) as async_client:
                collected: list[EntityFile] = []
                token: str | None = None
                while True:
                    resp = await async_client.files.list(
                        person_id=PersonId(person_id), page_size=page_size, page_token=token
                    )
                    collected.extend(resp.data)
                    if max_files is not None and len(collected) >= max_files:
                        collected[:] = collected[:max_files]
                        break
                    if not resp.next_page_token:
                        break
                    token = resp.next_page_token

                sem = asyncio.Semaphore(max(1, concurrency))

                class ManifestFile(TypedDict):
                    fileId: int
                    name: str
                    contentType: str | None
                    size: int
                    createdAt: object
                    uploaderId: int
                    path: str

                manifest_files: list[ManifestFile] = []

                with ProgressManager(
                    settings=ProgressSettings(mode=ctx.progress, quiet=ctx.quiet)
                ) as pm:

                    async def download_one(f: EntityFile) -> None:
                        async with sem:
                            safe_name = sanitize_filename(f.name)
                            dest = files_dir / f"{int(f.id)}__{safe_name}"
                            _task_id, cb = pm.task(
                                description=f"download {f.name}",
                                total_bytes=int(f.size) if f.size else None,
                            )
                            await async_client.files.download_to(
                                f.id,
                                dest,
                                overwrite=overwrite,
                                on_progress=cb,
                                timeout=ctx.timeout,
                            )
                            manifest_files.append(
                                {
                                    "fileId": int(f.id),
                                    "name": f.name,
                                    "contentType": f.content_type,
                                    "size": f.size,
                                    "createdAt": f.created_at,
                                    "uploaderId": int(f.uploader_id),
                                    "path": str(dest.relative_to(entity_dir)),
                                }
                            )

                    await asyncio.gather(*(download_one(f) for f in collected))

                manifest = {
                    "entity": {"type": "person", "personId": person_id},
                    "files": sorted(manifest_files, key=lambda x: x["fileId"]),
                }
                (entity_dir / "manifest.json").write_text(
                    __import__("json").dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                nonlocal rate_limit_snapshot
                rate_limit_snapshot = async_client.rate_limits.snapshot()
                return {
                    "out": str(entity_dir),
                    "filesDownloaded": len(manifest_files),
                    "manifest": str((entity_dir / "manifest.json").relative_to(entity_dir)),
                }

        data = asyncio.run(run())
        return CommandOutput(
            data=data, warnings=warnings, api_called=True, rate_limit=rate_limit_snapshot
        )

    run_command(ctx, command="person files dump", fn=fn)
