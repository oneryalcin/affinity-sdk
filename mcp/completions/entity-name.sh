#!/usr/bin/env bash
# completions/entity-name.sh - Provides entity name suggestions (persons and companies)
set -euo pipefail

source "${MCPBASH_PROJECT_ROOT}/lib/common.sh"

json_bin="${MCPBASH_JSON_TOOL_BIN:-jq}"
if ! command -v "${json_bin}" &>/dev/null; then
    printf '[]\n'
    exit 0
fi

args_json="${MCP_COMPLETION_ARGS_JSON:-{}}"
prefix="$("${json_bin}" -r '(.query // .prefix // "")' <<<"${args_json}" 2>/dev/null || printf '')"

limit="${MCP_COMPLETION_LIMIT:-10}"
offset="${MCP_COMPLETION_OFFSET:-0}"
half_limit=$((limit / 2))

# Search persons and companies
suggestions='[]'

if [[ -n "$prefix" ]]; then
    # Search persons
    person_results=$(run_xaffinity_readonly person ls --query "$prefix" --max-results "$half_limit" --output json --quiet \
        ${AFFINITY_SESSION_CACHE:+--session-cache "$AFFINITY_SESSION_CACHE"} 2>/dev/null || echo '{"data":{"persons":[]}}')

    person_names=$(echo "$person_results" | "${json_bin}" -c '.data.persons[:'"$half_limit"'] | map(.firstName + " " + .lastName)')

    # Search companies
    company_results=$(run_xaffinity_readonly company ls --query "$prefix" --max-results "$half_limit" --output json --quiet \
        ${AFFINITY_SESSION_CACHE:+--session-cache "$AFFINITY_SESSION_CACHE"} 2>/dev/null || echo '{"data":{"companies":[]}}')

    company_names=$(echo "$company_results" | "${json_bin}" -c '.data.companies[:'"$half_limit"'] | map(.name)')

    # Combine and format
    suggestions=$(echo "$person_names" "$company_names" | "${json_bin}" -s 'add | unique | .[:'"$limit"']')
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
