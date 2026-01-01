#!/usr/bin/env bash
# tools/resolve-workflow-item/tool.sh - Resolve entity to list entry for workflow operations
set -euo pipefail

source "${MCP_SDK:?}/tool-sdk.sh"
source "${MCPBASH_PROJECT_ROOT}/lib/common.sh"
source "${MCPBASH_PROJECT_ROOT}/lib/entity-types.sh"

# Extract arguments
list_id="$(mcp_args_get '.listId // null')"
list_name="$(mcp_args_get '.listName // null')"
entity_json="$(mcp_args_get '.entity // null')"
entity_id="$(mcp_args_get '.entityId // null')"
entity_type="$(mcp_args_get '.entityType // null')"

# Resolve list
if [[ "$list_id" == "null" || -z "$list_id" ]]; then
    if [[ "$list_name" == "null" || -z "$list_name" ]]; then
        mcp_fail_invalid_args "Either listId or listName is required"
    fi
    list_id=$(resolve_list "$list_name") || mcp_fail_invalid_args "List not found: $list_name"
fi

# Parse entity reference
if [[ "$entity_json" != "null" ]]; then
    entity_type=$(echo "$entity_json" | jq -r '.type')
    entity_id=$(echo "$entity_json" | jq -r '.id')
elif [[ "$entity_id" == "null" || -z "$entity_id" ]]; then
    mcp_fail_invalid_args "Either entity object or entityId is required"
fi

# Search for list entries matching the entity
result=$(run_xaffinity_readonly list-entry ls --list-id "$list_id" --output json --quiet \
    ${AFFINITY_SESSION_CACHE:+--session-cache "$AFFINITY_SESSION_CACHE"} 2>/dev/null)

# Filter entries by entity ID
entries=$(echo "$result" | jq -c --argjson entityId "$entity_id" \
    '[.data.entries[] | select(.entityId == $entityId)]')

count=$(echo "$entries" | jq 'length')

if [[ "$count" == "0" ]]; then
    mcp_emit_json "$(jq -n \
        --argjson listId "$list_id" \
        --argjson entityId "$entity_id" \
        '{
            resolved: false,
            message: "Entity not found on this list",
            listId: $listId,
            entityId: $entityId,
            entries: []
        }'
    )"
    exit 0
fi

# Transform entries
items=$(echo "$entries" | jq -c 'map({
    listEntryId: .id,
    listId: .listId,
    entityId: .entityId,
    entityName: .entityName,
    status: .status,
    createdAt: .createdAt
})')

# If single entry, mark as resolved
if [[ "$count" == "1" ]]; then
    entry=$(echo "$items" | jq -c '.[0]')
    mcp_emit_json "$(jq -n \
        --argjson entry "$entry" \
        --argjson count "$count" \
        '{
            resolved: true,
            listEntryId: $entry.listEntryId,
            entry: $entry,
            count: $count
        }'
    )"
else
    # Multiple entries - return all candidates
    mcp_emit_json "$(jq -n \
        --argjson entries "$items" \
        --argjson count "$count" \
        '{
            resolved: false,
            message: "Multiple entries found - specify listEntryId directly",
            entries: $entries,
            count: $count
        }'
    )"
fi
