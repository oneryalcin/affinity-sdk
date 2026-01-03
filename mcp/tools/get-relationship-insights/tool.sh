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
    xaffinity_log_error "get-relationship-insights" "missing required target entity"
    mcp_fail_invalid_args "Either targetEntity or targetId is required"
fi

# Log tool invocation
xaffinity_log_debug "get-relationship-insights" "target_type=$target_type target_id=$target_id source_id=${source_id:-none}"

cli_args=(--output json --quiet)
[[ -n "${AFFINITY_SESSION_CACHE:-}" ]] && cli_args+=(--session-cache "$AFFINITY_SESSION_CACHE")

# Get relationship strength for target
target_strength="null"
if [[ "$target_type" == "person" ]]; then
    target_strength=$(run_xaffinity_readonly relationship-strength ls --external-id "$target_id" "${cli_args[@]}" 2>/dev/null | jq -c '.data.relationshipStrengths[0] // null' || echo "null")
fi

# Helper to fetch all interaction types for a person
fetch_all_interactions() {
    local person_id="$1"
    local max_results="$2"
    local tmp_dir
    tmp_dir=$(mktemp -d)

    for itype in email meeting call chat-message; do
        (
            result=$(run_xaffinity_readonly interaction ls --person-id "$person_id" --type "$itype" --max-results "$max_results" "${cli_args[@]}" 2>/dev/null || echo '{"data":{"interactions":[]}}')
            echo "$result" | jq -c '.data.interactions // []' > "$tmp_dir/$itype.json"
        ) &
    done
    wait

    cat "$tmp_dir"/*.json 2>/dev/null | jq -s 'add | sort_by(.date) | reverse' || echo "[]"
    rm -rf "$tmp_dir"
}

# Get shared connections (people who know both source and target)
shared_connections="[]"
intro_paths="[]"

if [[ "$source_id" != "null" && -n "$source_id" ]]; then
    # Get source's interactions to find common contacts (Affinity API requires type)
    source_interactions=$(fetch_all_interactions "$source_id" 100)

    # Get target's interactions
    target_interactions=$(fetch_all_interactions "$target_id" 100)

    # Find overlapping person IDs (potential intro paths)
    source_contacts=$(echo "$source_interactions" | jq -c '[.[] | (.participants // [])[] | .personId] | unique' || echo "[]")
    target_contacts=$(echo "$target_interactions" | jq -c '[.[] | (.participants // [])[] | .personId] | unique' || echo "[]")

    shared_connections=$(jq -n \
        --argjson source "$source_contacts" \
        --argjson target "$target_contacts" \
        '[$source[] as $s | $target[] | select(. == $s)] | unique | .[:10]' || echo "[]")
fi

# Get target's recent activity summary (Affinity API requires type)
recent_interactions=$(fetch_all_interactions "$target_id" 5)

# Log completion stats
shared_count=$(echo "$shared_connections" | jq 'length')
recent_count=$(echo "$recent_interactions" | jq 'length')
xaffinity_log_debug "get-relationship-insights" "completed shared_connections=$shared_count recent_interactions=$recent_count"

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
