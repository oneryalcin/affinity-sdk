#!/usr/bin/env bash
# tools/get-relationship-insights/tool.sh - Get relationship insights for warm intro paths
set -euo pipefail

source "${MCP_SDK:?}/tool-sdk.sh"
source "${MCPBASH_PROJECT_ROOT}/lib/common.sh"
source "${MCPBASH_PROJECT_ROOT}/lib/entity-types.sh"

# Extract arguments
target_entity_json="$(mcp_args_get '.targetEntity // null')"
target_id="$(mcp_args_get '.targetId // null')"
target_type="$(mcp_args_get '.targetType // "person"')"
source_id="$(mcp_args_get '.sourceId // null')"

# Parse target entity
if [[ "$target_entity_json" != "null" ]]; then
    target_type=$(echo "$target_entity_json" | jq -r '.type')
    target_id=$(echo "$target_entity_json" | jq -r '.id')
elif [[ "$target_id" == "null" || -z "$target_id" ]]; then
    mcp_fail_invalid_args "Either targetEntity or targetId is required"
fi

cli_args=(--output json --quiet)
[[ -n "${AFFINITY_SESSION_CACHE:-}" ]] && cli_args+=(--session-cache "$AFFINITY_SESSION_CACHE")

# Get relationship strength for target
target_strength="null"
if [[ "$target_type" == "person" ]]; then
    target_strength=$(run_xaffinity_readonly relationship-strength get "$target_id" "${cli_args[@]}" 2>/dev/null | jq -c '.data // null' || echo "null")
fi

# Get shared connections (people who know both source and target)
shared_connections="[]"
intro_paths="[]"

if [[ "$source_id" != "null" && -n "$source_id" ]]; then
    # Get source's interactions to find common contacts
    source_interactions=$(run_xaffinity_readonly interaction ls --person-id "$source_id" --max-results 100 "${cli_args[@]}" 2>/dev/null | jq -c '.data.interactions // []' || echo "[]")

    # Get target's interactions
    target_interactions=$(run_xaffinity_readonly interaction ls --person-id "$target_id" --max-results 100 "${cli_args[@]}" 2>/dev/null | jq -c '.data.interactions // []' || echo "[]")

    # Find overlapping person IDs (potential intro paths)
    source_contacts=$(echo "$source_interactions" | jq -c '[.[].participants[].personId] | unique')
    target_contacts=$(echo "$target_interactions" | jq -c '[.[].participants[].personId] | unique')

    shared_connections=$(jq -n \
        --argjson source "$source_contacts" \
        --argjson target "$target_contacts" \
        '[$source[] as $s | $target[] | select(. == $s)] | unique | .[:10]')
fi

# Get target's recent activity summary
recent_interactions=$(run_xaffinity_readonly interaction ls --person-id "$target_id" --max-results 5 "${cli_args[@]}" 2>/dev/null | jq -c '.data.interactions // []' || echo "[]")

mcp_emit_json "$(jq -n \
    --arg targetType "$target_type" \
    --argjson targetId "$target_id" \
    --argjson relationshipStrength "$target_strength" \
    --argjson sharedConnections "$shared_connections" \
    --argjson recentInteractions "$recent_interactions" \
    '{
        target: {type: $targetType, id: $targetId},
        relationshipStrength: $relationshipStrength,
        sharedConnections: $sharedConnections,
        recentActivity: $recentInteractions,
        introPathsAvailable: ($sharedConnections | length > 0)
    }'
)"
