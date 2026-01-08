#!/usr/bin/env bash
# resources/saved-views/saved-views.sh - Return saved views for a list
# Called by xaffinity.sh provider with listId as argument
set -euo pipefail

listId="${1:-}"
if [[ -z "${listId}" ]]; then
    echo "Usage: saved-views.sh <listId>" >&2
    exit 4
fi

# Get list details including saved views
output=$(xaffinity list get "${listId}" --json 2>&1) || {
    echo "Failed to get list ${listId}: ${output}" >&2
    exit 3
}

# Extract saved views array from the response
# Output format: array of {id, name, type}
echo "${output}" | "${MCPBASH_JSON_TOOL_BIN:-jq}" -c '
    .data.savedViews // [] |
    map({id, name, type}) |
    {
        listId: '"${listId}"',
        savedViews: .,
        note: "Saved view names only. Filter criteria are not available via API. Use --saved-view with exact name, or --filter for field-based filtering."
    }
'
