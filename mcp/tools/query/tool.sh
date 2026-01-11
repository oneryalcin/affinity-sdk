#!/usr/bin/env bash
# tools/query/tool.sh - Execute a structured JSON query against Affinity data
set -euo pipefail

source "${MCP_SDK:?}/tool-sdk.sh"
source "${MCPBASH_PROJECT_ROOT}/lib/common.sh"

# Parse arguments using mcp-bash SDK
query_json="$(mcp_args_require '.query' 'Query is required')"
dry_run="$(mcp_args_get '.dryRun // false')"
max_records="$(mcp_args_int '.maxRecords' --default 1000)"
timeout_secs="$(mcp_args_int '.timeout' --default 120)"
max_output_bytes="$(mcp_args_int '.maxOutputBytes' --default 50000)"

# Log tool invocation
xaffinity_log_debug "query" "dryRun=$dry_run maxRecords=$max_records timeout=$timeout_secs"

# Track start time for latency metrics
_get_time_ms() { local t; t=$(date +%s%3N 2>/dev/null); [[ "$t" =~ ^[0-9]+$ ]] && echo "$t" || echo "$(($(date +%s) * 1000))"; }
start_time_ms=$(_get_time_ms)

# Validate query has required 'from' field
if ! printf '%s' "$query_json" | jq_tool -e '.from' >/dev/null 2>&1; then
    mcp_result_error '{"type": "validation_error", "message": "Query must have a \"from\" field specifying the entity type"}'
    exit 0
fi

# Cap max_records at 10000 for safety
if [[ $max_records -gt 10000 ]]; then
    max_records=10000
fi

# Build command array (stdin-based: query JSON is piped in)
declare -a cmd_args=("xaffinity" "query")
cmd_args+=("--max-records" "$max_records")
cmd_args+=("--timeout" "$timeout_secs")

if [[ "$dry_run" == "true" ]]; then
    cmd_args+=("--dry-run")
fi

# Report initial progress
if [[ "$dry_run" == "true" ]]; then
    mcp_progress 0 "Planning query execution"
else
    mcp_progress 0 "Executing query"
fi

# Check for cancellation before execution
if mcp_is_cancelled; then
    mcp_result_error '{"type": "cancelled", "message": "Operation cancelled by client"}'
    exit 0
fi

# Execute and capture stdout/stderr separately
stdout_file=$(mktemp)
stderr_file=$(mktemp)
trap 'rm -f "$stdout_file" "$stderr_file"' EXIT

# Execute CLI with query on stdin (CLI handles timeout via --timeout flag)
set +e
printf '%s' "$query_json" | "${cmd_args[@]}" >"$stdout_file" 2>"$stderr_file"
exit_code=$?
set -e

stdout_content=$(cat "$stdout_file")
stderr_content=$(cat "$stderr_file")

# Build executed command for transparency (without the actual query for brevity)
cmd_json=$(jq_tool -n --args '$ARGS.positional' -- "${cmd_args[@]}")

# Check for cancellation after execution
if mcp_is_cancelled; then
    mcp_result_error '{"type": "cancelled", "message": "Operation cancelled by client"}'
    exit 0
fi

# Calculate latency
end_time_ms=$(_get_time_ms)
latency_ms=$((end_time_ms - start_time_ms))

# Log result and metrics
xaffinity_log_debug "query" "exit_code=$exit_code output_bytes=${#stdout_content} latency_ms=$latency_ms"
log_metric "query_latency_ms" "$latency_ms" "dryRun=$dry_run" "status=$([[ $exit_code -eq 0 ]] && echo 'success' || echo 'error')"
log_metric "query_output_bytes" "${#stdout_content}" "dryRun=$dry_run"

# Report completion progress
mcp_progress 100 "Complete"

if [[ $exit_code -eq 0 ]]; then
    # Validate stdout is valid JSON before using --argjson
    if mcp_is_valid_json "$stdout_content"; then
        # Apply semantic truncation
        if truncated_result=$(mcp_json_truncate "$stdout_content" "$max_output_bytes"); then
            mcp_result_success "$(printf '%s' "$truncated_result" | jq_tool --argjson cmd "$cmd_json" '. + {executed: $cmd}')"
        else
            # Truncation failed (output too large, can't truncate safely)
            mcp_result_error "$(printf '%s' "$truncated_result" | jq_tool --argjson cmd "$cmd_json" '.error + {executed: $cmd}')"
        fi
    else
        # Use temp files to avoid "Argument list too long" error with large outputs
        printf '%s' "$stdout_content" > "$stdout_file"
        mcp_result_error "$(jq_tool -n --rawfile stdout "$stdout_file" --argjson cmd "$cmd_json" \
            '{type: "invalid_json_output", message: "CLI returned non-JSON output", output: $stdout, executed: $cmd}')"
    fi
else
    # Use temp files to avoid "Argument list too long" error with large outputs
    printf '%s' "$stderr_content" > "$stderr_file"
    printf '%s' "$stdout_content" > "$stdout_file"
    mcp_result_error "$(jq_tool -n --rawfile stderr "$stderr_file" --rawfile stdout "$stdout_file" \
          --argjson cmd "$cmd_json" --argjson code "$exit_code" \
          '{type: "cli_error", message: $stderr, output: $stdout, exitCode: $code, executed: $cmd}')"
fi
