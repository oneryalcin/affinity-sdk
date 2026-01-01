#!/usr/bin/env bash
# tools/add-note/tool.sh - Add a note to an entity
set -euo pipefail

source "${MCP_SDK:?}/tool-sdk.sh"
source "${MCPBASH_PROJECT_ROOT}/lib/common.sh"
source "${MCPBASH_PROJECT_ROOT}/lib/entity-types.sh"

# Extract arguments
content="$(mcp_args_require '.content' 'Note content is required')"
entity_json="$(mcp_args_get '.entity // null')"
entity_type="$(mcp_args_get '.entityType // null')"
entity_id="$(mcp_args_get '.entityId // null')"
creator_id="$(mcp_args_get '.creatorId // null')"

# Parse entity reference
if [[ "$entity_json" != "null" ]]; then
    entity_type=$(echo "$entity_json" | jq -r '.type')
    entity_id=$(echo "$entity_json" | jq -r '.id')
elif [[ "$entity_id" == "null" || -z "$entity_id" ]]; then
    mcp_fail_invalid_args "Either entity object or entityId/entityType is required"
fi

validate_entity_type "$entity_type" || mcp_fail_invalid_args "Invalid entity type: $entity_type"

# Build note create command
note_args=(--content "$content" --"$entity_type"-id "$entity_id" --output json --quiet)
[[ -n "${AFFINITY_SESSION_CACHE:-}" ]] && note_args+=(--session-cache "$AFFINITY_SESSION_CACHE")
[[ "$creator_id" != "null" && -n "$creator_id" ]] && note_args+=(--creator-id "$creator_id")

# Create the note
result=$(run_xaffinity note create "${note_args[@]}" 2>&1) || {
    mcp_fail -32603 "Failed to create note: $result"
}

note_data=$(echo "$result" | jq -c '.data // {}')
note_id=$(echo "$note_data" | jq -r '.id // "unknown"')

mcp_emit_json "$(jq -n \
    --arg noteId "$note_id" \
    --arg entityType "$entity_type" \
    --argjson entityId "$entity_id" \
    --argjson note "$note_data" \
    '{
        success: true,
        noteId: $noteId,
        entity: {type: $entityType, id: $entityId},
        note: $note
    }'
)"
