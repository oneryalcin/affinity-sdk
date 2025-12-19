from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TypedDict

import click
import rich_click

from affinity import AsyncAffinity
from affinity.models.entities import Company
from affinity.models.rate_limit_snapshot import RateLimitSnapshot
from affinity.models.secondary import EntityFile
from affinity.models.types import V1_BASE_URL, V2_BASE_URL
from affinity.types import CompanyId

from ..context import CLIContext
from ..csv_utils import sanitize_filename
from ..options import output_options
from ..progress import ProgressManager, ProgressSettings
from ..runner import CommandOutput, run_command


@click.group(name="company", cls=rich_click.RichGroup)
def company_group() -> None:
    """Company commands."""


@company_group.command(name="search", cls=rich_click.RichCommand)
@click.argument("query")
@click.option("--page-size", type=int, default=None, help="v1 page size (max 500).")
@click.option("--page-token", type=str, default=None, help="v1 page token for resuming.")
@click.option("--max-results", type=int, default=None, help="Stop after N results total.")
@click.option("--all", "all_pages", is_flag=True, help="Fetch all pages.")
@output_options
@click.pass_obj
def company_search(
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
            resp = client.companies.search(
                query,
                with_interaction_dates=True,
                page_size=page_size,
                page_token=next_token,
            )
            fetched_first_page = True
            for company in resp.data:
                results.append(_company_row(company))
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

    run_command(ctx, command="company search", fn=fn)


def _company_row(company: Company) -> dict[str, object]:
    last_interaction = None
    if company.interaction_dates is not None:
        last_interaction = company.interaction_dates.last_interaction_date
    return {
        "id": int(company.id),
        "name": company.name,
        "domain": company.domain,
        "domains": company.domains,
        "lastInteractionDate": last_interaction,
    }


@company_group.group(name="files", cls=rich_click.RichGroup)
def company_files_group() -> None:
    """Company files."""


@company_files_group.command(name="dump", cls=rich_click.RichCommand)
@click.argument("company_id", type=int)
@click.option("--out", "out_dir", type=click.Path(), default=None)
@click.option("--overwrite", is_flag=True, help="Overwrite existing files.")
@click.option("--concurrency", type=int, default=3, show_default=True)
@click.option("--page-size", type=int, default=200, show_default=True)
@click.option("--max-files", type=int, default=None, help="Stop after N files.")
@output_options
@click.pass_obj
def company_files_dump(
    ctx: CLIContext,
    company_id: int,
    *,
    out_dir: str | None,
    overwrite: bool,
    concurrency: int,
    page_size: int,
    max_files: int | None,
) -> None:
    def fn(ctx: CLIContext, warnings: list[str]) -> CommandOutput:
        ctx.load_dotenv_if_requested()
        api_key = ctx.resolve_api_key(warnings=warnings)

        entity_dir = (
            Path(out_dir)
            if out_dir is not None
            else Path.cwd() / f"affinity-company-{company_id}-files"
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
                        organization_id=CompanyId(company_id),
                        page_size=page_size,
                        page_token=token,
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
                    "entity": {"type": "company", "companyId": company_id},
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

    run_command(ctx, command="company files dump", fn=fn)
