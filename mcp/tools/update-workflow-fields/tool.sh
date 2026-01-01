#!/usr/bin/env bash
# tools/update-workflow-fields/tool.sh - Update multiple fields on a workflow item
set -euo pipefail

source "${MCP_SDK:?}/tool-sdk.sh"
source "${MCPBASH_PROJECT_ROOT}/lib/common.sh"
source "${MCPBASH_PROJECT_ROOT}/lib/field-resolution.sh"

# Extract arguments
list_id="$(mcp_args_require '.listId' 'listId is required')"
list_entry_id="$(mcp_args_require '.listEntryId' 'listEntryId is required')"
fields_json="$(mcp_args_require '.fields' 'fields object is required')"

# Get workflow config for field resolution
config=$(get_or_fetch_workflow_config "$list_id")

# Parse fields object - expecting {fieldName: value, ...} or {fieldId: value, ...}
field_updates=$(echo "$fields_json" | jq -c 'to_entries')

# Track results
results='[]'
errors='[]'

# Process each field update
while IFS= read -r entry; do
    field_key=$(echo "$entry" | jq -r '.key')
    value=$(echo "$entry" | jq -r '.value')

    # Resolve field name to ID if needed
    if [[ "$field_key" =~ ^[0-9]+$ ]]; then
        field_id="$field_key"
    else
        field_id=$(resolve_field_id "$list_id" "$field_key") || {
            errors=$(echo "$errors" | jq -c --arg key "$field_key" '. + [{field: $key, error: "Field not found"}]')
            continue
        }
    fi

    # Update the field
    update_result=$(run_xaffinity field-value set \
        --list-entry-id "$list_entry_id" \
        --field-id "$field_id" \
        --value "$value" \
        --output json --quiet \
        ${AFFINITY_SESSION_CACHE:+--session-cache "$AFFINITY_SESSION_CACHE"} 2>&1) && {
        results=$(echo "$results" | jq -c --arg key "$field_key" --arg fid "$field_id" \
            '. + [{field: $key, fieldId: $fid, success: true}]')
    } || {
        errors=$(echo "$errors" | jq -c --arg key "$field_key" --arg err "$update_result" \
            '. + [{field: $key, error: $err}]')
    }
done < <(echo "$field_updates" | jq -c '.[]')

success_count=$(echo "$results" | jq 'length')
error_count=$(echo "$errors" | jq 'length')

mcp_emit_json "$(jq -n \
    --argjson listId "$list_id" \
    --argjson listEntryId "$list_entry_id" \
    --argjson results "$results" \
    --argjson errors "$errors" \
    --argjson successCount "$success_count" \
    --argjson errorCount "$error_count" \
    '{
        success: ($errorCount == 0),
        listId: $listId,
        listEntryId: $listEntryId,
        updated: $results,
        errors: $errors,
        summary: {updated: $successCount, failed: $errorCount}
    }'
)"
