#!/usr/bin/env bash
# tools/get-entity-dossier/tool.sh - Get comprehensive dossier for an entity
set -euo pipefail

source "${MCP_SDK:?}/tool-sdk.sh"
source "${MCPBASH_PROJECT_ROOT}/lib/common.sh"
source "${MCPBASH_PROJECT_ROOT}/lib/entity-types.sh"

# Extract arguments
entity_json="$(mcp_args_get '.entity // null')"
entity_type="$(mcp_args_get '.entityType // null')"
entity_id="$(mcp_args_get '.entityId // null')"
include_interactions="$(mcp_args_get '.includeInteractions // true')"
include_notes="$(mcp_args_get '.includeNotes // true')"
include_lists="$(mcp_args_get '.includeLists // true')"

# Parse entity reference
if [[ "$entity_json" != "null" ]]; then
    entity_type=$(echo "$entity_json" | jq -r '.type')
    entity_id=$(echo "$entity_json" | jq -r '.id')
elif [[ "$entity_id" == "null" || -z "$entity_id" ]]; then
    mcp_fail_invalid_args "Either entity object or entityId/entityType is required"
fi

validate_entity_type "$entity_type" || mcp_fail_invalid_args "Invalid entity type: $entity_type"

# Fetch entity details
cli_args=(--output json --quiet)
[[ -n "${AFFINITY_SESSION_CACHE:-}" ]] && cli_args+=(--session-cache "$AFFINITY_SESSION_CACHE")

case "$entity_type" in
    person)
        entity_data=$(run_xaffinity_readonly person get "$entity_id" "${cli_args[@]}" 2>/dev/null | jq -c '.data.person // {}')
        ;;
    company)
        entity_data=$(run_xaffinity_readonly company get "$entity_id" "${cli_args[@]}" 2>/dev/null | jq -c '.data.company // {}')
        ;;
    opportunity)
        entity_data=$(run_xaffinity_readonly opportunity get "$entity_id" "${cli_args[@]}" 2>/dev/null | jq -c '.data.opportunity // {}')
        ;;
esac

# Get relationship strength if person
relationship_data="null"
if [[ "$entity_type" == "person" ]]; then
    relationship_data=$(run_xaffinity_readonly relationship-strength ls --external-id "$entity_id" "${cli_args[@]}" 2>/dev/null | jq -c '.data.relationshipStrengths[0] // null' || echo "null")
fi

# Get interactions if requested
interactions="[]"
if [[ "$include_interactions" == "true" ]]; then
    interactions=$(run_xaffinity_readonly interaction ls --"$entity_type"-id "$entity_id" --max-results 10 "${cli_args[@]}" 2>/dev/null | jq -c '.data.interactions // []' || echo "[]")
fi

# Get notes if requested
notes="[]"
if [[ "$include_notes" == "true" ]]; then
    notes=$(run_xaffinity_readonly note ls --"$entity_type"-id "$entity_id" --max-results 10 "${cli_args[@]}" 2>/dev/null | jq -c '.data.notes // []' || echo "[]")
fi

# Get list memberships if requested
lists="[]"
if [[ "$include_lists" == "true" ]]; then
    lists=$(run_xaffinity_readonly list-entry ls --"$entity_type"-id "$entity_id" "${cli_args[@]}" 2>/dev/null | jq -c '.data.entries // []' || echo "[]")
fi

# Build dossier
mcp_emit_json "$(jq -n \
    --arg entityType "$entity_type" \
    --argjson entityId "$entity_id" \
    --argjson entity "$entity_data" \
    --argjson relationship "$relationship_data" \
    --argjson interactions "$interactions" \
    --argjson notes "$notes" \
    --argjson lists "$lists" \
    '{
        entity: {type: $entityType, id: $entityId},
        details: $entity,
        relationshipStrength: $relationship,
        recentInteractions: $interactions,
        recentNotes: $notes,
        listMemberships: $lists
    }'
)"
