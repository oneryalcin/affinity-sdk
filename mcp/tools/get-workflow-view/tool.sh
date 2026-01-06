#!/usr/bin/env bash
# tools/get-workflow-view/tool.sh - Get items from a workflow view or list
set -euo pipefail

source "${MCP_SDK:?}/tool-sdk.sh"
source "${MCPBASH_PROJECT_ROOT}/lib/common.sh"

# Extract arguments
list_id="$(mcp_args_get '.listId // null')"
list_name="$(mcp_args_get '.listName // null')"
view_id="$(mcp_args_get '.viewId // null')"
view_name="$(mcp_args_get '.viewName // null')"
limit="$(mcp_args_int '.limit' --default 50 --min 1 --max 500)"

# Resolve list
if [[ "$list_id" == "null" || -z "$list_id" ]]; then
    if [[ "$list_name" == "null" || -z "$list_name" ]]; then
        mcp_fail_invalid_args "Either listId or listName is required"
    fi
    list_id=$(resolve_list "$list_name") || mcp_fail_invalid_args "List not found: $list_name"
fi

# Get workflow config for context
config=$(get_or_fetch_workflow_config "$list_id")
list_type=$(echo "$config" | jq_tool -r '.list.type')

# Build export command arguments (list export takes list_id as positional arg)
export_args=(--output json --quiet --max-results "$limit")
[[ -n "${AFFINITY_SESSION_CACHE:-}" ]] && export_args+=(--session-cache "$AFFINITY_SESSION_CACHE")

# Resolve view if specified
if [[ "$view_id" != "null" && -n "$view_id" ]]; then
    export_args+=(--saved-view "$view_id")
elif [[ "$view_name" != "null" && -n "$view_name" ]]; then
    # Find view ID by name
    actual_view_id=$(echo "$config" | jq_tool -r --arg name "$view_name" \
        '.savedViews[] | select(.name == $name) | .viewId' | head -1)
    if [[ -n "$actual_view_id" ]]; then
        export_args+=(--saved-view "$actual_view_id")
    fi
fi

# Export list entries
result=$(run_xaffinity_readonly list export "$list_id" "${export_args[@]}" 2>/dev/null)

# Transform entries to workflow items (CLI uses .data.rows with fields at root level)
items=$(echo "$result" | jq_tool -c '
    .data.rows // [] | map({
        listEntryId: .listEntryId,
        entity: {
            type: .entityType,
            id: .entityId
        },
        entityName: .entityName,
        status: (.Status // null),
        fields: (. | to_entries | map(select(.key | test("^(listEntryId|entityType|entityId|entityName)$") | not)) | from_entries)
    })
')

count=$(echo "$items" | jq_tool 'length')
list_name_display=$(echo "$config" | jq_tool -r '.list.name')

mcp_emit_json "$(jq_tool -n \
    --argjson items "$items" \
    --argjson listId "$list_id" \
    --arg listName "$list_name_display" \
    --arg listType "$list_type" \
    --argjson count "$count" \
    '{
        items: $items,
        list: {listId: $listId, name: $listName, type: $listType},
        count: $count
    }'
)"
