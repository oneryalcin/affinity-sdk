#!/usr/bin/env bash
# providers/xaffinity.sh - Custom provider for xaffinity:// URI scheme
# Executes resource scripts under resources/ to generate dynamic content.
#
# Environment variables passed by mcp-bash framework (v0.8.4+):
#   MCPBASH_HOME          - Framework installation directory
#   MCPBASH_PROJECT_ROOT  - Project root directory
#   MCPBASH_PROVIDERS_DIR - Providers directory (project or framework)
#   MCP_RESOURCES_ROOTS   - Allowed resource roots (colon-separated)

set -euo pipefail

uri="${1:-}"
if [ -z "${uri}" ]; then
    printf '%s\n' "xaffinity provider requires xaffinity://<path>" >&2
    exit 4
fi

case "${uri}" in
xaffinity://*)
    # Extract path from URI (e.g., "me" from "xaffinity://me")
    resource_path="${uri#xaffinity://}"
    ;;
*)
    printf '%s\n' "Unsupported URI scheme for xaffinity provider" >&2
    exit 4
    ;;
esac

# Map URI path to script
# xaffinity://me -> resources/me/me.sh
# xaffinity://me/person-id -> resources/me-person-id/me-person-id.sh
# xaffinity://interaction-enums -> resources/interaction-enums/interaction-enums.json
# xaffinity://saved-views/{listId} -> resources/saved-views/saved-views.sh {listId}
# xaffinity://workflow-config/{listId} -> resources/workflow-config/workflow-config.sh {listId}
# xaffinity://field-catalogs/{entityType} -> resources/field-catalogs/field-catalogs.sh {entityType}

# Use project resources directory
resources_dir="${MCPBASH_PROJECT_ROOT}/resources"

# Handle parameterized URIs (e.g., saved-views/{listId})
# Check for known parameterized patterns before normalizing
script_path=""
script_args=()

case "${resource_path}" in
    saved-views/*)
        # Extract listId from saved-views/{listId}
        param="${resource_path#saved-views/}"
        if [[ -n "${param}" && -f "${resources_dir}/saved-views/saved-views.sh" ]]; then
            script_path="${resources_dir}/saved-views/saved-views.sh"
            script_args=("${param}")
        fi
        ;;
    workflow-config/*)
        # Extract listId from workflow-config/{listId}
        param="${resource_path#workflow-config/}"
        if [[ -n "${param}" && -f "${resources_dir}/workflow-config/workflow-config.sh" ]]; then
            script_path="${resources_dir}/workflow-config/workflow-config.sh"
            script_args=("${param}")
        fi
        ;;
    field-catalogs/*)
        # Extract entityType from field-catalogs/{entityType}
        param="${resource_path#field-catalogs/}"
        if [[ -n "${param}" && -f "${resources_dir}/field-catalogs/field-catalogs.sh" ]]; then
            script_path="${resources_dir}/field-catalogs/field-catalogs.sh"
            script_args=("${param}")
        fi
        ;;
esac

# If not a parameterized path, use standard resolution
if [ -z "${script_path}" ]; then
    # Normalize path: replace / with - for directory lookup
    normalized_path="${resource_path//\//-}"

    # Try to find the resource script or static file
    if [ -f "${resources_dir}/${normalized_path}/${normalized_path}.sh" ]; then
        script_path="${resources_dir}/${normalized_path}/${normalized_path}.sh"
    elif [ -f "${resources_dir}/${normalized_path}/${normalized_path}.json" ]; then
        # Static JSON file - just output it
        cat "${resources_dir}/${normalized_path}/${normalized_path}.json"
        exit 0
    elif [ -f "${resources_dir}/${normalized_path}/${normalized_path}.md" ]; then
        # Static markdown file - just output it
        cat "${resources_dir}/${normalized_path}/${normalized_path}.md"
        exit 0
    elif [ -f "${resources_dir}/${resource_path}/${resource_path##*/}.sh" ]; then
        # Try with original path structure
        script_path="${resources_dir}/${resource_path}/${resource_path##*/}.sh"
    fi
fi

if [ -z "${script_path}" ] || [ ! -f "${script_path}" ]; then
    printf '%s\n' "Resource not found: ${resource_path}" >&2
    exit 3
fi

# Execute the resource script
# The script should output JSON content
if [ -x "${script_path}" ]; then
    exec "${script_path}" "${script_args[@]}"
else
    # Fall back to bash execution if not marked executable
    exec bash "${script_path}" "${script_args[@]}"
fi
