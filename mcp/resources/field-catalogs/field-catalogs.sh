#!/usr/bin/env bash
# resources/field-catalogs/field-catalogs.sh - Return field catalog for an entity type or list
# entityType can be: a listId (numeric), list name, "company", "person", or "opportunity"
set -euo pipefail

entityType="${1:-}"
if [[ -z "${entityType}" ]]; then
    echo "Usage: field-catalogs.sh <entityType|listId|listName>" >&2
    exit 4
fi

jq_tool="${MCPBASH_JSON_TOOL_BIN:-jq}"

# Resolve list name to ID if not numeric and not a known entity type
listId=""
if [[ "${entityType}" =~ ^[0-9]+$ ]]; then
    listId="${entityType}"
elif [[ ! "${entityType}" =~ ^(company|companies|person|persons|people|opportunity|opportunities)$ ]]; then
    # Try to resolve as list name
    lists_output=$(xaffinity list ls --json 2>&1) || {
        echo "Failed to fetch lists: ${lists_output}" >&2
        exit 3
    }
    listId=$(echo "${lists_output}" | "$jq_tool" -r --arg name "${entityType}" '
        .data.lists[] | select(.name == $name) | .id // empty
    ')
    if [[ -z "${listId}" ]]; then
        echo "Unknown entity type or list name: ${entityType}. Use a list ID (numeric), list name, 'company', 'person', or 'opportunity'." >&2
        exit 4
    fi
fi

# Handle list ID (numeric or resolved from name)
if [[ -n "${listId}" ]]; then
    # List ID - get list-specific fields
    fields_output=$(xaffinity field ls --list-id "${listId}" --json 2>&1) || {
        echo "Failed to get fields for list ${listId}: ${fields_output}" >&2
        exit 3
    }

    echo "${fields_output}" | "$jq_tool" -c --arg listId "${listId}" '
        {
            entityType: "list",
            listId: ($listId | tonumber),
            fields: (.data.fields // [] | map({
                id: .id,
                name: .name,
                valueType: .valueType,
                enrichmentSource: .enrichmentSource,
                dropdownOptions: (if .dropdownOptions then .dropdownOptions else null end)
            }) | map(if .dropdownOptions == null then del(.dropdownOptions) else . end)),
            note: "Use field names in --filter expressions: --filter '\''FieldName=\"Value\"'\''"
        }
    '
else
    # Global entity type - return fixed schema info
    case "${entityType}" in
        company|companies)
            "$jq_tool" -n '{
                entityType: "company",
                fields: [
                    {name: "id", type: "integer", description: "Unique company ID"},
                    {name: "name", type: "string", description: "Company name"},
                    {name: "domain", type: "string", description: "Company domain/website"},
                    {name: "domains", type: "array", description: "All associated domains"},
                    {name: "global", type: "boolean", description: "Whether company is global (not list-specific)"}
                ],
                note: "Global company fields are fixed. List-specific fields are on list entries - use field-catalogs/{listId} for those."
            }'
            ;;
        person|persons|people)
            "$jq_tool" -n '{
                entityType: "person",
                fields: [
                    {name: "id", type: "integer", description: "Unique person ID"},
                    {name: "firstName", type: "string", description: "First name"},
                    {name: "lastName", type: "string", description: "Last name"},
                    {name: "primaryEmail", type: "string", description: "Primary email address"},
                    {name: "emails", type: "array", description: "All email addresses"}
                ],
                note: "Global person fields are fixed. List-specific fields are on list entries - use field-catalogs/{listId} for those."
            }'
            ;;
        opportunity|opportunities)
            "$jq_tool" -n '{
                entityType: "opportunity",
                note: "Opportunities are list-specific. Use field-catalogs/{listId} or field-catalogs/{listName} with a pipeline list to see opportunity fields."
            }'
            ;;
    esac
fi
