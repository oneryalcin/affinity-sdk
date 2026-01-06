#!/usr/bin/env bash
# tools/find-entities/tool.sh - Search for persons, companies, or opportunities
set -euo pipefail

source "${MCP_SDK:?}/tool-sdk.sh"
source "${MCPBASH_PROJECT_ROOT}/lib/common.sh"
source "${MCPBASH_PROJECT_ROOT}/lib/entity-types.sh"

# Extract arguments
query="$(mcp_args_require '.query' 'Query string is required')"
types_json="$(mcp_args_get '.types // ["person", "company"]')"
limit="$(mcp_args_int '.limit' --default 10 --min 1 --max 100)"

# Log tool invocation (debug mode only, query is logged as it's the search term)
xaffinity_log_debug "find-entities" "query='$query' types=$types_json limit=$limit"

# Parse types array (bash 3.2 compatible)
types=()
while IFS= read -r item; do
    [[ -n "$item" ]] && types+=("$item")
done < <(echo "$types_json" | jq_tool -r '.[]')

# Create temp directory for parallel results
tmp_dir=$(mktemp -d)
trap 'rm -rf "$tmp_dir"' EXIT

# Progress: 3 steps (start search, wait for results, merge)
mcp_progress 0 "Searching ${#types[@]} entity types" 3

xaffinity_log_debug "find-entities" "searching ${#types[@]} entity types in parallel"

# Search each requested type in PARALLEL using background jobs
for entity_type in "${types[@]}"; do
    validate_entity_type "$entity_type" || continue

    (
        case "$entity_type" in
            person)
                result=$(run_xaffinity_readonly person ls --query "$query" --output json --quiet \
                    ${AFFINITY_SESSION_CACHE:+--session-cache "$AFFINITY_SESSION_CACHE"} \
                    2>/dev/null | jq_tool -c '.data.persons // []' || echo "[]")
                ;;
            company)
                result=$(run_xaffinity_readonly company ls --query "$query" --output json --quiet \
                    ${AFFINITY_SESSION_CACHE:+--session-cache "$AFFINITY_SESSION_CACHE"} \
                    2>/dev/null | jq_tool -c '.data.companies // []' || echo "[]")
                ;;
            opportunity)
                # Opportunities cannot be searched globally in Affinity API
                # They can only be accessed via list export or saved views
                result="[]"
                ;;
        esac

        # Transform to unified format
        echo "$result" | jq_tool -c --arg type "$entity_type" '
            .[:'"$limit"'] | map({
                entity: {type: $type, id: .id},
                displayName: (.name // ((.firstName // "") + " " + (.lastName // "")) // "Unknown"),
                headline: .headline,
                primaryEmail: (if .emails then .emails[0] else .primaryEmail end),
                domain: .domain
            })
        ' > "$tmp_dir/$entity_type.json"
    ) &
done

# Wait for all parallel searches to complete
mcp_progress 1 "Waiting for search results" 3
wait

# Check for cancellation before merging
if mcp_is_cancelled; then
    mcp_fail -32001 "Operation cancelled"
fi

# Merge results from all entity types
mcp_progress 2 "Merging results" 3
all_matches=$(cat "$tmp_dir"/*.json 2>/dev/null | jq_tool -s 'add // [] | .[:'"$limit"']' || echo "[]")

# Generate human-readable summary
count=$(echo "$all_matches" | jq_tool 'length')
notes="Found $count matches for '$query'"

xaffinity_log_debug "find-entities" "completed with $count matches"

mcp_progress 3 "Search complete" 3

mcp_emit_json "$(jq_tool -n \
    --argjson matches "$all_matches" \
    --arg notes "$notes" \
    '{matches: $matches, notes: $notes}'
)"
