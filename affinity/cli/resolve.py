from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from affinity.exceptions import NotFoundError
from affinity.models.entities import AffinityList, FieldMetadata, SavedView
from affinity.types import ListId, SavedViewId

from .errors import CLIError


@dataclass(frozen=True, slots=True)
class ResolvedList:
    list: AffinityList
    resolved: dict[str, Any]


def _looks_int(value: str) -> bool:
    return value.isdigit()


def resolve_list_selector(
    *,
    client: Any,
    selector: str,
) -> ResolvedList:
    selector = selector.strip()
    if _looks_int(selector):
        list_id = ListId(int(selector))
        lst = client.lists.get(list_id)
        return ResolvedList(list=lst, resolved={"list": {"input": selector, "listId": int(lst.id)}})

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
    return ResolvedList(list=lst, resolved={"list": {"input": selector, "listId": int(lst.id)}})


def resolve_saved_view(
    *,
    client: Any,
    list_id: ListId,
    selector: str,
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

    views = list_all_saved_views(client=client, list_id=list_id)
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


def list_all_saved_views(*, client: Any, list_id: ListId) -> list[SavedView]:
    return list(client.lists.saved_views_all(list_id))


def list_fields_for_list(*, client: Any, list_id: ListId) -> list[FieldMetadata]:
    return cast(list[FieldMetadata], client.lists.get_fields(list_id))
