#!/usr/bin/env bash
# resources/workflow-config/workflow-config.sh - Return workflow configuration for a list
# Includes status field options and saved views
set -euo pipefail

listId="${1:-}"
if [[ -z "${listId}" ]]; then
    echo "Usage: workflow-config.sh <listId>" >&2
    exit 4
fi

jq_tool="${MCPBASH_JSON_TOOL_BIN:-jq}"

# Get list details including saved views
list_output=$(xaffinity list get "${listId}" --json 2>&1) || {
    echo "Failed to get list ${listId}: ${list_output}" >&2
    exit 3
}

# Get fields for the list to find status/dropdown fields
fields_output=$(xaffinity field ls --list-id "${listId}" --json 2>&1) || {
    echo "Failed to get fields for list ${listId}: ${fields_output}" >&2
    exit 3
}

# Extract list info, saved views, and status-like fields (dropdowns)
echo "${list_output}" | "$jq_tool" -c --argjson fields "$(echo "${fields_output}" | "$jq_tool" -c '.data.fields // []')" '
    .data.list as $list |
    .data.savedViews as $savedViews |
    {
        listId: $list.id,
        listName: $list.name,
        listType: $list.type,
        savedViews: ($savedViews // [] | map({id, name, type})),
        statusFields: (
            $fields
            | map(select(.valueType == "dropdown" or .valueType == "status"))
            | map({
                id: .id,
                name: .name,
                valueType: .valueType,
                options: (.dropdownOptions // [])
            })
        ),
        note: "Use saved view names with --saved-view, or filter by status field values with --filter '\''FieldName=\"Value\"'\''"
    }
'
