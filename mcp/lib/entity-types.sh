#!/usr/bin/env bash
# lib/entity-types.sh - Entity reference handling

# Parse EntityRef JSON and extract components
# Input: {"type": "person", "id": 123}
parse_entity_ref() {
    local json="$1"
    local field="${2:-}"

    if [[ -n "$field" ]]; then
        echo "$json" | jq_tool -r ".$field // empty"
    else
        echo "$json"
    fi
}

# Validate entity type
validate_entity_type() {
    local type="$1"
    case "$type" in
        person|company|opportunity) return 0 ;;
        *) return 1 ;;
    esac
}

# Build EntityRef JSON
build_entity_ref() {
    local type="$1"
    local id="$2"
    jq_tool -n --arg t "$type" --argjson i "$id" '{type: $t, id: $i}'
}

# Build ListEntryRef JSON
build_list_entry_ref() {
    local list_id="$1"
    local entry_id="$2"
    jq_tool -n --argjson l "$list_id" --argjson e "$entry_id" '{listId: $l, listEntryId: $e}'
}

# Parse WorkflowItemRef - handles both forms:
# Preferred: {"listId": 456, "listEntryId": 789}
# Convenience: {"listId": 456, "entity": {"type": "person", "id": 123}}
parse_workflow_item_ref() {
    local json="$1"

    local list_id=$(echo "$json" | jq_tool -r '.listId // empty')
    local list_entry_id=$(echo "$json" | jq_tool -r '.listEntryId // empty')

    if [[ -n "$list_id" && -n "$list_entry_id" ]]; then
        # Preferred form - direct list entry reference
        echo "$json"
        return 0
    fi

    # Convenience form - need to resolve entity to list entry
    local entity=$(echo "$json" | jq_tool -c '.entity // null')
    if [[ "$entity" != "null" && -n "$list_id" ]]; then
        local entity_type=$(echo "$entity" | jq_tool -r '.type')
        local entity_id=$(echo "$entity" | jq_tool -r '.id')

        # Need to resolve - this requires the calling tool to handle
        jq_tool -n \
            --argjson listId "$list_id" \
            --arg entityType "$entity_type" \
            --argjson entityId "$entity_id" \
            '{listId: $listId, entity: {type: $entityType, id: $entityId}, needsResolution: true}'
        return 0
    fi

    echo "null"
    return 1
}

# Get CLI entity type flag
# Converts entity type to xaffinity CLI flag
get_entity_cli_type() {
    local type="$1"
    case "$type" in
        person) echo "person" ;;
        company) echo "company" ;;
        opportunity) echo "opportunity" ;;
        *) echo "" ;;
    esac
}
