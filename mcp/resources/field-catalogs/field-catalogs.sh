#!/usr/bin/env bash
# resources/field-catalogs/field-catalogs.sh - Return field catalog for an entity type or list
# entityType can be: a listId (numeric), "company", "person", or "opportunity"
set -euo pipefail

entityType="${1:-}"
if [[ -z "${entityType}" ]]; then
    echo "Usage: field-catalogs.sh <entityType|listId>" >&2
    exit 4
fi

jq_tool="${MCPBASH_JSON_TOOL_BIN:-jq}"

# Check if entityType is a list ID (numeric) or global entity type
if [[ "${entityType}" =~ ^[0-9]+$ ]]; then
    # List ID - get list-specific fields
    fields_output=$(xaffinity field ls --list-id "${entityType}" --json 2>&1) || {
        echo "Failed to get fields for list ${entityType}: ${fields_output}" >&2
        exit 3
    }

    echo "${fields_output}" | "$jq_tool" -c --arg listId "${entityType}" '
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
                note: "Opportunities are list-specific. Use field-catalogs/{listId} with a pipeline list ID to see opportunity fields."
            }'
            ;;
        *)
            echo "Unknown entity type: ${entityType}. Use a list ID (numeric), 'company', 'person', or 'opportunity'." >&2
            exit 4
            ;;
    esac
fi
