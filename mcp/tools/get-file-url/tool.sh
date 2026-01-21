#!/usr/bin/env bash
# tools/get-file-url/tool.sh - Get presigned URL for file download
set -euo pipefail

source "${MCP_SDK:?}/tool-sdk.sh"
source "${MCPBASH_PROJECT_ROOT}/lib/common.sh"

# Extract file ID argument
file_id="$(mcp_args_get '.fileId')"

# Validate required argument
if [[ -z "$file_id" || "$file_id" == "null" ]]; then
    mcp_fail_invalid_args "fileId is required. Get file IDs from 'company files ls', 'person files ls', or 'opportunity files ls' commands."
fi

# Log tool invocation
xaffinity_log_debug "get-file-url" "fileId=$file_id"

# Build CLI arguments
cli_args=(--output json --quiet)
[[ -n "${AFFINITY_SESSION_CACHE:-}" ]] && cli_args+=(--session-cache "$AFFINITY_SESSION_CACHE")

# Call the CLI command
mcp_progress 0 "Getting presigned URL" 1

result=$(run_xaffinity_readonly file-url "$file_id" "${cli_args[@]}" 2>&1) || {
    xaffinity_log_error "get-file-url" "CLI failed: $result"
    mcp_fail -32603 "Failed to get file URL: $result"
}

mcp_progress 1 "Done" 1

# Extract and return the data portion
mcp_emit_json "$(echo "$result" | jq_tool -c '.data')"
