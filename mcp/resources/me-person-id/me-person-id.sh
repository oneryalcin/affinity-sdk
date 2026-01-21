#!/usr/bin/env bash
# resources/me-person-id/resource.sh - Get current user's person ID (cached)
# In Affinity, user.id from whoami IS the person ID
set -euo pipefail

source "${MCPBASH_PROJECT_ROOT}/lib/common.sh"
source "${MCPBASH_PROJECT_ROOT}/lib/cache.sh"

# Try cache first
if person_id=$(get_me_person_id_cached 2>/dev/null); then
    echo "{\"personId\": $person_id}"
    exit 0
fi

cli_args=(--json)
[[ -n "${AFFINITY_SESSION_CACHE:-}" ]] && cli_args+=(--session-cache "$AFFINITY_SESSION_CACHE")

# Get current user from whoami - user.id IS the person ID
# Capture stderr to include actual CLI error in failure message
stderr_file=$(mktemp)
trap 'rm -f "$stderr_file"' EXIT

if ! result=$(run_xaffinity_readonly whoami "${cli_args[@]}" 2>"$stderr_file"); then
    cli_error=$(cat "$stderr_file" 2>/dev/null | head -c 500 || echo "unknown error")
    echo "Error: Failed to get current user: $cli_error" >&2
    exit 1
fi

person_id=$(echo "$result" | jq_tool -r '.data.user.id // empty')

if [[ -n "$person_id" ]]; then
    # Cache for future requests
    set_me_person_id_cached "$person_id"
    echo "{\"personId\": $person_id}"
else
    echo '{"error": "Could not get current user ID - user.id missing from response"}'
    exit 1
fi
