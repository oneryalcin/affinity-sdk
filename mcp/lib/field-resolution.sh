#!/usr/bin/env bash
# lib/field-resolution.sh - Field name to ID resolution

# Resolve field name to field ID within a list context
# Usage: resolve_field_id <list_id> <field_name>
resolve_field_id() {
    local list_id="$1"
    local field_name="$2"

    # Get workflow config (cached)
    local config
    config=$(get_or_fetch_workflow_config "$list_id")

    # Search field index
    local field_id
    field_id=$(echo "$config" | jq_tool -r --arg name "$field_name" \
        '.fieldIndex[] | select(.name == $name) | .fieldId' | head -1)

    if [[ -n "$field_id" ]]; then
        echo "$field_id"
        return 0
    fi

    # Try case-insensitive match
    field_id=$(echo "$config" | jq_tool -r --arg name "$field_name" \
        '.fieldIndex[] | select(.name | ascii_downcase == ($name | ascii_downcase)) | .fieldId' | head -1)

    if [[ -n "$field_id" ]]; then
        echo "$field_id"
        return 0
    fi

    return 1
}

# Resolve status option text to option ID
# Usage: resolve_status_option_id <list_id> <status_text>
resolve_status_option_id() {
    local list_id="$1"
    local status_text="$2"

    # Get workflow config (cached)
    local config
    config=$(get_or_fetch_workflow_config "$list_id")

    # Get status field options
    local status_field
    status_field=$(echo "$config" | jq_tool -c '.statusField // null')

    if [[ "$status_field" == "null" ]]; then
        return 1
    fi

    # Find matching option
    local option_id
    option_id=$(echo "$status_field" | jq_tool -r --arg text "$status_text" \
        '.options[] | select(.text == $text) | .id' | head -1)

    if [[ -n "$option_id" ]]; then
        echo "$option_id"
        return 0
    fi

    # Try case-insensitive match
    option_id=$(echo "$status_field" | jq_tool -r --arg text "$status_text" \
        '.options[] | select(.text | ascii_downcase == ($text | ascii_downcase)) | .id' | head -1)

    if [[ -n "$option_id" ]]; then
        echo "$option_id"
        return 0
    fi

    return 1
}

# Get all status options for a list
# Usage: get_status_options <list_id>
get_status_options() {
    local list_id="$1"

    local config
    config=$(get_or_fetch_workflow_config "$list_id")

    echo "$config" | jq_tool -c '.statusField.options // []'
}

# Resolve field value for update
# Handles special cases like dropdowns, dates, etc.
# Usage: resolve_field_value <list_id> <field_id> <value>
resolve_field_value() {
    local list_id="$1"
    local field_id="$2"
    local value="$3"

    local config
    config=$(get_or_fetch_workflow_config "$list_id")

    # Get field type
    local field_info
    field_info=$(echo "$config" | jq_tool -c --arg fid "$field_id" \
        '.fieldIndex[] | select(.fieldId == $fid)')

    local value_type
    value_type=$(echo "$field_info" | jq_tool -r '.valueType // "text"')

    case "$value_type" in
        ranked-dropdown|dropdown)
            # Need to resolve to option ID
            # For now, pass through - the CLI handles resolution
            echo "$value"
            ;;
        date|datetime)
            # Ensure ISO format
            echo "$value"
            ;;
        number)
            echo "$value"
            ;;
        *)
            # Text and other types - pass through
            echo "$value"
            ;;
    esac
}
