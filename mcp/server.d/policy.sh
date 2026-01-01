#!/usr/bin/env bash
# server.d/policy.sh - Tool execution policies for xaffinity MCP Server

# Read-only tools (safe for any context)
AFFINITY_MCP_TOOLS_READONLY="find-entities find-lists get-list-workflow-config get-workflow-view resolve-workflow-item get-entity-dossier get-relationship-insights get-status-timeline get-interactions read-xaffinity-resource"

# Write tools (require full access)
AFFINITY_MCP_TOOLS_WRITE="set-workflow-status update-workflow-fields add-note log-interaction"

# All tools
AFFINITY_MCP_TOOLS_ALL="${AFFINITY_MCP_TOOLS_READONLY} ${AFFINITY_MCP_TOOLS_WRITE}"

# Policy check function called by the framework
mcp_tools_policy_check() {
    local tool_name="$1"

    # If read-only mode is enabled, only allow read-only tools
    if [[ "${AFFINITY_MCP_READ_ONLY:-}" == "1" ]]; then
        case " ${AFFINITY_MCP_TOOLS_READONLY} " in
            *" ${tool_name} "*) return 0 ;;
            *) return 1 ;;
        esac
    fi

    # Full access mode - allow all tools
    case " ${AFFINITY_MCP_TOOLS_ALL} " in
        *" ${tool_name} "*) return 0 ;;
        *) return 1 ;;
    esac
}
