#!/usr/bin/env bash
# tools/find-entities/tool.sh - Search for persons, companies, or opportunities
set -euo pipefail

source "${MCP_SDK:?}/tool-sdk.sh"
source "${MCPBASH_PROJECT_ROOT}/lib/common.sh"
source "${MCPBASH_PROJECT_ROOT}/lib/entity-types.sh"

# Extract arguments
query="$(mcp_args_require '.query' 'Query string is required')"
types_json="$(mcp_args_get '.types // ["person", "company"]')"
limit="$(mcp_args_get '.limit // 10')"

# Log tool invocation (debug mode only, query is logged as it's the search term)
xaffinity_log_debug "find-entities" "query='$query' types=$types_json limit=$limit"

# Parse types array (bash 3.2 compatible)
types=()
while IFS= read -r item; do
    [[ -n "$item" ]] && types+=("$item")
done < <(echo "$types_json" | jq -r '.[]')

# Create temp directory for parallel results
tmp_dir=$(mktemp -d)
trap 'rm -rf "$tmp_dir"' EXIT

xaffinity_log_debug "find-entities" "searching ${#types[@]} entity types in parallel"

# Search each requested type in PARALLEL using background jobs
for entity_type in "${types[@]}"; do
    validate_entity_type "$entity_type" || continue

    (
        case "$entity_type" in
            person)
                result=$(run_xaffinity_readonly person ls --query "$query" --output json --quiet \
                    ${AFFINITY_SESSION_CACHE:+--session-cache "$AFFINITY_SESSION_CACHE"} \
                    2>/dev/null | jq -c '.data.persons // []' || echo "[]")
                ;;
            company)
                result=$(run_xaffinity_readonly company ls --query "$query" --output json --quiet \
                    ${AFFINITY_SESSION_CACHE:+--session-cache "$AFFINITY_SESSION_CACHE"} \
                    2>/dev/null | jq -c '.data.companies // []' || echo "[]")
                ;;
            opportunity)
                # Opportunities cannot be searched globally in Affinity API
                # They can only be accessed via list export or saved views
                result="[]"
                ;;
        esac

        # Transform to unified format
        echo "$result" | jq -c --arg type "$entity_type" '
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
wait

# Merge results from all entity types
all_matches=$(cat "$tmp_dir"/*.json 2>/dev/null | jq -s 'add // [] | .[:'"$limit"']' || echo "[]")

# Generate human-readable summary
count=$(echo "$all_matches" | jq 'length')
notes="Found $count matches for '$query'"

xaffinity_log_debug "find-entities" "completed with $count matches"

mcp_emit_json "$(jq -n \
    --argjson matches "$all_matches" \
    --arg notes "$notes" \
    '{matches: $matches, notes: $notes}'
)"
