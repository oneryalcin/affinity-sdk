#!/usr/bin/env bash
# server.d/policy.sh - Tool execution policies for xaffinity MCP Server

# Read-only tools (safe for any context)
# Includes CLI Gateway read tools: discover-commands, execute-read-command
AFFINITY_MCP_TOOLS_READONLY="get-entity-dossier read-xaffinity-resource query discover-commands execute-read-command"

# Write tools (require full access)
# Includes CLI Gateway write tool: execute-write-command
AFFINITY_MCP_TOOLS_WRITE="execute-write-command"

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
