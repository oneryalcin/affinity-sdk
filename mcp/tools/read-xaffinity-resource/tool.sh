#!/usr/bin/env bash
# tools/read-xaffinity-resource/tool.sh - Read xaffinity:// resources
# Workaround for MCP clients with limited resource support (e.g., Cursor)
set -euo pipefail

source "${MCP_SDK:?}/tool-sdk.sh"

# Parse input using SDK
uri="$(mcp_args_require '.uri' 'uri parameter is required')"

# Validate URI scheme
if [[ "$uri" != xaffinity://* ]]; then
    mcp_error "URI must start with xaffinity://"
fi

# Delegate to the xaffinity provider
provider_script="${MCPBASH_PROJECT_ROOT}/providers/xaffinity.sh"

if [[ ! -f "$provider_script" ]]; then
    mcp_error "xaffinity provider not found"
fi

exec "$provider_script" "$uri"
