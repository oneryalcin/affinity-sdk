#!/usr/bin/env bash
# tools/get-interactions/tool.sh - Get interactions for an entity
set -euo pipefail

source "${MCP_SDK:?}/tool-sdk.sh"
source "${MCPBASH_PROJECT_ROOT}/lib/common.sh"
source "${MCPBASH_PROJECT_ROOT}/lib/entity-types.sh"

# Extract arguments
entity_json="$(mcp_args_get '.entity // null')"
entity_type="$(mcp_args_get '.entityType // null')"
entity_id="$(mcp_args_get '.entityId // null')"
interaction_type="$(mcp_args_get '.type // null')"
limit="$(mcp_args_get '.limit // 20')"

# Parse entity reference
if [[ "$entity_json" != "null" ]]; then
    entity_type=$(echo "$entity_json" | jq -r '.type')
    entity_id=$(echo "$entity_json" | jq -r '.id')
elif [[ "$entity_id" == "null" || -z "$entity_id" ]]; then
    mcp_fail_invalid_args "Either entity object or entityId/entityType is required"
fi

validate_entity_type "$entity_type" || mcp_fail_invalid_args "Invalid entity type: $entity_type"

# Build list command
int_args=(--"$entity_type"-id "$entity_id" --max-results "$limit" --output json --quiet)
[[ -n "${AFFINITY_SESSION_CACHE:-}" ]] && int_args+=(--session-cache "$AFFINITY_SESSION_CACHE")
[[ "$interaction_type" != "null" && -n "$interaction_type" ]] && int_args+=(--type "$interaction_type")

# Get interactions
result=$(run_xaffinity_readonly interaction ls "${int_args[@]}" 2>/dev/null)

interactions=$(echo "$result" | jq -c '.data.interactions // []')

# Transform to summary format
items=$(echo "$interactions" | jq -c 'map({
    interactionId: .id,
    type: .type,
    direction: .direction,
    subject: .subject,
    date: .date,
    participants: [.participants[].personId],
    createdAt: .createdAt
})')

count=$(echo "$items" | jq 'length')

mcp_emit_json "$(jq -n \
    --arg entityType "$entity_type" \
    --argjson entityId "$entity_id" \
    --argjson interactions "$items" \
    --argjson count "$count" \
    '{
        entity: {type: $entityType, id: $entityId},
        interactions: $interactions,
        count: $count
    }'
)"
