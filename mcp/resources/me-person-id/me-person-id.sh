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
result=$(run_xaffinity_readonly whoami "${cli_args[@]}" 2>/dev/null)
person_id=$(echo "$result" | jq_tool -r '.data.user.id // empty')

if [[ -n "$person_id" ]]; then
    # Cache for future requests
    set_me_person_id_cached "$person_id"
    echo "{\"personId\": $person_id}"
else
    echo '{"error": "Could not get current user ID"}'
    exit 1
fi
