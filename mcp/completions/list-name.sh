#!/usr/bin/env bash
# completions/list-name.sh - Provides list name suggestions
set -euo pipefail

source "${MCPBASH_PROJECT_ROOT}/lib/common.sh"

json_bin="${MCPBASH_JSON_TOOL_BIN:-jq}"
if ! command -v "${json_bin}" &>/dev/null; then
    printf '[]\n'
    exit 0
fi

args_json="${MCP_COMPLETION_ARGS_JSON:-{}}"
prefix="$("${json_bin}" -r '(.query // .prefix // "")' <<<"${args_json}" 2>/dev/null || printf '')"

limit="${MCP_COMPLETION_LIMIT:-20}"
offset="${MCP_COMPLETION_OFFSET:-0}"

# Fetch all lists
result=$(run_xaffinity_readonly list ls --output json --quiet \
    ${AFFINITY_SESSION_CACHE:+--session-cache "$AFFINITY_SESSION_CACHE"} 2>/dev/null || echo '{"data":{"lists":[]}}')

# Filter by prefix and extract names
suggestions=$(echo "$result" | "${json_bin}" -c --arg prefix "$prefix" '
    .data.lists |
    [.[] | select(.name | ascii_downcase | contains($prefix | ascii_downcase))] |
    map(.name) |
    unique
')

# Apply pagination
"${json_bin}" -n -c \
    --argjson suggestions "$suggestions" \
    --argjson limit "$limit" \
    --argjson offset "$offset" '
        ($suggestions[$offset:$offset+$limit]) as $page
        | {
            suggestions: $page,
            hasMore: (($offset + ($page | length)) < ($suggestions | length)),
            next: (if (($offset + ($page | length)) < ($suggestions | length)) then $offset + ($page | length) else null end)
        }
    '
