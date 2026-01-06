#!/usr/bin/env bash
# resources/me/me.sh - Get current user information
set -euo pipefail

source "${MCPBASH_PROJECT_ROOT}/lib/common.sh"

cli_args=(--json)
[[ -n "${AFFINITY_SESSION_CACHE:-}" ]] && cli_args+=(--session-cache "$AFFINITY_SESSION_CACHE")

# Get current user (whoami)
result=$(run_xaffinity_readonly whoami "${cli_args[@]}" 2>/dev/null) || {
    echo '{"error": "Failed to get current user"}' >&2
    exit 1
}

echo "$result" | jq_tool -c '.data // {}'
