#!/usr/bin/env bash
# completions/status-value.sh - Provides status option suggestions for a list
set -euo pipefail

source "${MCPBASH_PROJECT_ROOT}/lib/common.sh"

json_bin="${MCPBASH_JSON_TOOL_BIN:-jq}"
if ! command -v "${json_bin}" &>/dev/null; then
    printf '[]\n'
    exit 0
fi

args_json="${MCP_COMPLETION_ARGS_JSON:-{}}"
prefix="$("${json_bin}" -r '(.query // .prefix // "")' <<<"${args_json}" 2>/dev/null || printf '')"
list_id="$("${json_bin}" -r '.listId // ""' <<<"${args_json}" 2>/dev/null || printf '')"

limit="${MCP_COMPLETION_LIMIT:-20}"
offset="${MCP_COMPLETION_OFFSET:-0}"

suggestions='[]'

if [[ -n "$list_id" ]]; then
    # Get workflow config for the list
    config=$(get_or_fetch_workflow_config "$list_id" 2>/dev/null || echo '{}')

    # Extract status options
    suggestions=$(echo "$config" | "${json_bin}" -c --arg prefix "$prefix" '
        .statusField.options // [] |
        [.[] | select(.text | ascii_downcase | contains($prefix | ascii_downcase))] |
        map(.text) |
        unique
    ')
fi

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
