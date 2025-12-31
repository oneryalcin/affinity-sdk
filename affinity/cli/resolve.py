from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from affinity import Affinity
from affinity.exceptions import NotFoundError
from affinity.models.entities import AffinityList, FieldMetadata, SavedView
from affinity.types import ListId, SavedViewId

from .errors import CLIError

if TYPE_CHECKING:
    from .session_cache import SessionCache


@dataclass(frozen=True, slots=True)
class ResolvedList:
    list: AffinityList
    resolved: dict[str, Any]


def _looks_int(value: str) -> bool:
    return value.isdigit()


def resolve_list_selector(
    *,
    client: Affinity,
    selector: str,
    cache: SessionCache | None = None,
) -> ResolvedList:
    """Resolve list by name/ID with optional session cache support."""
    selector = selector.strip()

    # ID lookups don't benefit from name resolution cache
    if _looks_int(selector):
        list_id = ListId(int(selector))
        lst = client.lists.get(list_id)
        return ResolvedList(list=lst, resolved={"list": {"input": selector, "listId": int(lst.id)}})

    cache_key = f"list_resolve_{selector.lower()}_any"

    if cache and cache.enabled:
        cached = cache.get(cache_key, AffinityList)
        if cached is not None:
            return ResolvedList(
                list=cached,
                resolved={"list": {"input": selector, "listId": int(cached.id), "cached": True}},
            )

    matches = client.lists.resolve_all(name=selector)
    if not matches:
        raise CLIError(
            f'List not found: "{selector}"',
            exit_code=4,
            error_type="not_found",
            details={"selector": selector},
        )
    if len(matches) > 1:
        raise CLIError(
            f'Ambiguous list name: "{selector}" ({len(matches)} matches)',
            exit_code=2,
            error_type="ambiguous_resolution",
            details={
                "selector": selector,
                "matches": [
                    {"listId": int(m.id), "name": m.name, "type": m.type} for m in matches[:20]
                ],
            },
        )

    lst = matches[0]

    if cache and cache.enabled:
        cache.set(cache_key, lst)

    return ResolvedList(list=lst, resolved={"list": {"input": selector, "listId": int(lst.id)}})


def resolve_saved_view(
    *,
    client: Affinity,
    list_id: ListId,
    selector: str,
    cache: SessionCache | None = None,
) -> tuple[SavedView, dict[str, Any]]:
    selector = selector.strip()
    if _looks_int(selector):
        view_id = SavedViewId(int(selector))
        try:
            v = client.lists.get_saved_view(list_id, view_id)
        except NotFoundError as exc:
            raise CLIError(
                f"Saved view not found: {selector}",
                exit_code=4,
                error_type="not_found",
                details={"listId": int(list_id), "selector": selector},
            ) from exc
        return v, {
            "savedView": {
                "input": selector,
                "savedViewId": int(v.id),
                "name": v.name,
            }
        }

    views = list_all_saved_views(client=client, list_id=list_id, cache=cache)
    exact = [v for v in views if v.name.lower() == selector.lower()]
    if not exact:
        raise CLIError(
            f'Saved view not found: "{selector}"',
            exit_code=4,
            error_type="not_found",
            details={"listId": int(list_id), "selector": selector},
        )
    if len(exact) > 1:
        raise CLIError(
            f'Ambiguous saved view name: "{selector}"',
            exit_code=2,
            error_type="ambiguous_resolution",
            details={
                "listId": int(list_id),
                "selector": selector,
                "matches": [{"savedViewId": int(v.id), "name": v.name} for v in exact[:20]],
            },
        )
    v = exact[0]
    return v, {"savedView": {"input": selector, "savedViewId": int(v.id), "name": v.name}}


def list_all_saved_views(
    *,
    client: Affinity,
    list_id: ListId,
    cache: SessionCache | None = None,
) -> list[SavedView]:
    """Get saved views for a list with optional session cache support.

    Note: This caches the full list of saved views. If the fetch is
    interrupted mid-pagination, the cache won't be populated.
    """
    cache_key = f"saved_views_{list_id}"

    if cache and cache.enabled:
        cached = cache.get_list(cache_key, SavedView)
        if cached is not None:
            return cached

    # Eagerly evaluate paginated iterator to cache complete list
    # Note: If pagination is interrupted (e.g., network error), no partial
    # result is cached - the next call will retry from scratch
    views = list(client.lists.saved_views_all(list_id))

    if cache and cache.enabled:
        cache.set(cache_key, views)

    return views


def list_fields_for_list(
    *,
    client: Affinity,
    list_id: ListId,
    cache: SessionCache | None = None,
) -> list[FieldMetadata]:
    """Get list fields with optional session cache support."""
    cache_key = f"list_fields_{list_id}"

    if cache and cache.enabled:
        cached = cache.get_list(cache_key, FieldMetadata)
        if cached is not None:
            return cached

    fields = client.lists.get_fields(list_id)

    if cache and cache.enabled:
        cache.set(cache_key, fields)

    return fields


def get_person_fields(
    *,
    client: Affinity,
    cache: SessionCache | None = None,
) -> list[FieldMetadata]:
    """Get global person fields with optional session cache support."""
    cache_key = "person_fields_global"

    if cache and cache.enabled:
        cached = cache.get_list(cache_key, FieldMetadata)
        if cached is not None:
            return cached

    fields = client.persons.get_fields()

    if cache and cache.enabled:
        cache.set(cache_key, fields)

    return fields


def get_company_fields(
    *,
    client: Affinity,
    cache: SessionCache | None = None,
) -> list[FieldMetadata]:
    """Get global company fields with optional session cache support."""
    cache_key = "company_fields_global"

    if cache and cache.enabled:
        cached = cache.get_list(cache_key, FieldMetadata)
        if cached is not None:
            return cached

    fields = client.companies.get_fields()

    if cache and cache.enabled:
        cache.set(cache_key, fields)

    return fields
