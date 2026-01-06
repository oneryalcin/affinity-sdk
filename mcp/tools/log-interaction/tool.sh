#!/usr/bin/env bash
# tools/log-interaction/tool.sh - Log an interaction (call, meeting, email, etc.)
set -euo pipefail

source "${MCP_SDK:?}/tool-sdk.sh"
source "${MCPBASH_PROJECT_ROOT}/lib/common.sh"
source "${MCPBASH_PROJECT_ROOT}/lib/cache.sh"

# Extract arguments
interaction_type="$(mcp_args_require '.type' 'Interaction type is required')"
person_ids_json="$(mcp_args_get '.personIds // []')"
subject="$(mcp_args_get '.subject // null')"
body="$(mcp_args_get '.body // null')"
date="$(mcp_args_get '.date // null')"
direction="$(mcp_args_get '.direction // null')"

# Validate interaction type
case "$interaction_type" in
    call|meeting|email|chat_message|in_person) ;;
    *) mcp_fail_invalid_args "Invalid interaction type: $interaction_type. Must be one of: call, meeting, email, chat_message, in_person" ;;
esac

# Parse person IDs array
person_ids=()
while IFS= read -r id; do
    [[ -n "$id" ]] && person_ids+=("$id")
done < <(echo "$person_ids_json" | jq_tool -r '.[]')

if [[ ${#person_ids[@]} -eq 0 ]]; then
    mcp_fail_invalid_args "At least one person ID is required"
fi

# Build interaction create command
int_args=(--type "$interaction_type" --output json --quiet)
[[ -n "${AFFINITY_SESSION_CACHE:-}" ]] && int_args+=(--session-cache "$AFFINITY_SESSION_CACHE")

# Add person IDs
for pid in "${person_ids[@]}"; do
    int_args+=(--person-id "$pid")
done

# Add optional fields
[[ "$subject" != "null" && -n "$subject" ]] && int_args+=(--subject "$subject")
[[ "$body" != "null" && -n "$body" ]] && int_args+=(--body "$body")
[[ "$date" != "null" && -n "$date" ]] && int_args+=(--date "$date")
[[ "$direction" != "null" && -n "$direction" ]] && int_args+=(--direction "$direction")

# Create the interaction
result=$(run_xaffinity interaction create "${int_args[@]}" 2>&1) || {
    mcp_fail -32603 "Failed to log interaction: $result"
}

int_data=$(echo "$result" | jq_tool -c '.data // {}')
int_id=$(echo "$int_data" | jq_tool -r '.id // "unknown"')

mcp_emit_json "$(jq_tool -n \
    --arg interactionId "$int_id" \
    --arg type "$interaction_type" \
    --argjson personIds "$person_ids_json" \
    --argjson interaction "$int_data" \
    '{
        success: true,
        interactionId: $interactionId,
        type: $type,
        personIds: $personIds,
        interaction: $interaction
    }'
)"
