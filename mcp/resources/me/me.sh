#!/usr/bin/env bash
# resources/me/me.sh - Get current user information
set -euo pipefail

source "${MCPBASH_PROJECT_ROOT}/lib/common.sh"

cli_args=(--json)
[[ -n "${AFFINITY_SESSION_CACHE:-}" ]] && cli_args+=(--session-cache "$AFFINITY_SESSION_CACHE")

# Get current user (whoami)
# Capture stderr to include actual CLI error in failure message
stderr_file=$(mktemp)
trap 'rm -f "$stderr_file"' EXIT

if ! result=$(run_xaffinity_readonly whoami "${cli_args[@]}" 2>"$stderr_file"); then
    cli_error=$(cat "$stderr_file" 2>/dev/null | head -c 500 || echo "unknown error")
    echo "Error: Failed to get current user: $cli_error" >&2
    exit 1
fi

echo "$result" | jq_tool -c '.data // {}'
