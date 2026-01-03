#!/usr/bin/env bash
# tools/find-lists/tool.sh - Search for Affinity lists by name or type
set -euo pipefail

source "${MCP_SDK:?}/tool-sdk.sh"
source "${MCPBASH_PROJECT_ROOT}/lib/common.sh"

# Extract arguments
query="$(mcp_args_get '.query // ""')"
list_type="$(mcp_args_get '.type // null')"
limit="$(mcp_args_int '.limit' 20 1 100)"

# Fetch all lists
result=$(run_xaffinity_readonly list ls --output json --quiet \
    ${AFFINITY_SESSION_CACHE:+--session-cache "$AFFINITY_SESSION_CACHE"} 2>/dev/null)

# Filter by type if specified
if [[ "$list_type" != "null" && -n "$list_type" ]]; then
    lists=$(echo "$result" | jq -c --arg type "$list_type" \
        '.data.lists | [.[] | select(.type == $type)]')
else
    lists=$(echo "$result" | jq -c '.data.lists // []')
fi

# Filter by query if specified
if [[ -n "$query" ]]; then
    lists=$(echo "$lists" | jq -c --arg query "$query" \
        '[.[] | select(.name | ascii_downcase | contains($query | ascii_downcase))]')
fi

# Apply limit and transform
matches=$(echo "$lists" | jq -c '
    .[:'"$limit"'] | map({
        listId: .id,
        name: .name,
        type: .type,
        creatorId: .creatorId,
        public: .public
    })
')

count=$(echo "$matches" | jq 'length')
notes="Found $count lists"
if [[ -n "$query" ]]; then
    notes="$notes matching '$query'"
fi
if [[ "$list_type" != "null" && -n "$list_type" ]]; then
    notes="$notes (type: $list_type)"
fi

mcp_emit_json "$(jq -n \
    --argjson lists "$matches" \
    --arg notes "$notes" \
    '{lists: $lists, notes: $notes}'
)"
