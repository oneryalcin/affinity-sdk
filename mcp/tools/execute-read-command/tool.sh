#!/usr/bin/env bash
# tools/execute-read-command/tool.sh - Execute a read-only CLI command
set -euo pipefail

source "${MCP_SDK:?}/tool-sdk.sh"
source "${MCPBASH_PROJECT_ROOT}/lib/common.sh"
source "${MCPBASH_PROJECT_ROOT}/lib/cli-gateway.sh"

# Validate registry (required for CLI Gateway tools)
if ! validate_registry; then
    # validate_registry already emitted mcp_result_error with details
    exit 0
fi

# Debug: Log args state to help diagnose intermittent "Command is required" errors
# (See issue: args_json was sometimes empty despite valid request)
args_raw="$(mcp_args_raw)"
args_len="${#args_raw}"
xaffinity_log_debug "execute-read-command" "args_len=$args_len"

# Parse arguments using mcp-bash SDK
# Provide diagnostic info if command is missing
if ! command="$(mcp_args_get '.command')"; then
    mcp_result_error "$(jq_tool -n --argjson len "$args_len" \
        '{type: "validation_error", message: "Command is required", diagnostic: {argsLength: $len, hint: "If argsLength is 0, arguments were not passed to tool subprocess"}}')"
    exit 0
fi
if [[ -z "$command" || "$command" == "null" ]]; then
    # Extract first 200 chars of args for debugging (without secrets)
    args_preview="${args_raw:0:200}"
    mcp_result_error "$(jq_tool -n --argjson len "$args_len" --arg preview "$args_preview" \
        '{type: "validation_error", message: "Command is required (field missing or null)", diagnostic: {argsLength: $len, argsPreview: $preview}}')"
    exit 0
fi
argv_json="$(mcp_args_get '.argv // []')"
max_output_bytes="$(mcp_args_int '.maxOutputBytes' --default 50000)"
dry_run="$(mcp_args_get '.dryRun // false')"

# Log tool invocation
xaffinity_log_debug "execute-read-command" "command='$command' dryRun=$dry_run"

# Track start time for latency metrics (macOS doesn't support %3N, fall back to seconds)
_get_time_ms() { local t; t=$(date +%s%3N 2>/dev/null); [[ "$t" =~ ^[0-9]+$ ]] && echo "$t" || echo "$(($(date +%s) * 1000))"; }
start_time_ms=$(_get_time_ms)

# Validate command is in registry with category=read
validate_command "$command" "read" || exit 0

# Parse argv from JSON array
if [[ -z "$argv_json" ]]; then
    argv_json='[]'
fi
if ! printf '%s' "$argv_json" | jq_tool -e 'type == "array" and all(type == "string")' >/dev/null 2>&1; then
    mcp_result_error '{"type": "validation_error", "message": "argv must be an array of strings"}'
    exit 0
fi

# Use NUL-delimited extraction to preserve newlines inside argument strings
mapfile -d '' argv < <(printf '%s' "$argv_json" | jq_tool -jr '.[] + "\u0000"')

# Reject reserved flags that the tool appends automatically
for arg in "${argv[@]}"; do
    if [[ "$arg" == "--json" ]]; then
        mcp_result_error '{"type": "validation_error", "message": "--json is reserved; do not pass it in argv (tools append it automatically)"}'
        exit 0
    fi
done

# Validate argv against per-command schema
validate_argv "$command" "${argv[@]}" || exit 0

# Apply proactive limiting - inject/cap --limit for commands that support it
mapfile -d '' argv < <(apply_limit_cap "$command" "${argv[@]}")

# Build command array safely
declare -a cmd_args=("xaffinity")
read -ra parts <<< "$command"
cmd_args+=("${parts[@]}")
cmd_args+=("${argv[@]}")
cmd_args+=("--json")

# Check for cancellation before execution
if mcp_is_cancelled; then
    mcp_result_error '{"type": "cancelled", "message": "Operation cancelled by client"}'
    exit 0
fi

# Dry run: return what would be executed
if [[ "$dry_run" == "true" ]]; then
    mcp_result_success "$(jq_tool -n --args '$ARGS.positional' -- "${cmd_args[@]}" | \
        jq_tool '{result: null, dryRun: true, command: .}')"
    exit 0
fi

# Execute and capture stdout/stderr separately
stdout_file=$(mktemp)
stderr_file=$(mktemp)
trap 'rm -f "$stdout_file" "$stderr_file"' EXIT

# Check if command supports progress and MCP progress is available
supports_progress=false
if command_supports_progress "$command" && [[ -n "${MCP_PROGRESS_STREAM:-}" ]]; then
    supports_progress=true
    xaffinity_log_debug "execute-read-command" "Using progress forwarding for $command"
fi

# Report initial progress (only if not using CLI progress, to avoid duplicate 0%)
if [[ "$supports_progress" != "true" ]]; then
    mcp_progress 0 "Executing: ${command}"
fi

# Execute CLI with retry for transient failures (read commands are safe to retry)
set +e
if [[ "$supports_progress" == "true" ]]; then
    # Use progress-aware execution with --stderr-file to capture CLI errors (mcp-bash 0.9.11+)
    run_xaffinity_with_progress --stderr-file "$stderr_file" "${cmd_args[@]:1}" >"$stdout_file"
    exit_code=$?
else
    # Standard execution with retry
    mcp_with_retry 3 0.5 -- "${cmd_args[@]}" >"$stdout_file" 2>"$stderr_file"
    exit_code=$?
fi
set -e

stdout_content=$(cat "$stdout_file")
stderr_content=$(cat "$stderr_file")

# Build executed command array for transparency
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
xaffinity_log_debug "execute-read-command" "exit_code=$exit_code output_bytes=${#stdout_content} latency_ms=$latency_ms"
log_metric "cli_command_latency_ms" "$latency_ms" "command=$command" "status=$([[ $exit_code -eq 0 ]] && echo 'success' || echo 'error')" "category=read"
log_metric "cli_command_output_bytes" "${#stdout_content}" "command=$command"

# Report completion progress (skip if CLI already emitted via progress forwarding)
if [[ "$supports_progress" != "true" ]]; then
    mcp_progress 100 "Complete"
fi

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
    # CLI exited with error - use mcp-bash 0.9.12 helper to extract message
    printf '%s' "$stdout_content" > "$stdout_file"
    error_message=$(mcp_extract_cli_error "$stdout_content" "$stderr_content" "$exit_code")
    printf '%s' "$error_message" > "$stderr_file"
    mcp_result_error "$(jq_tool -n --rawfile message "$stderr_file" --rawfile stdout "$stdout_file" \
          --argjson cmd "$cmd_json" --argjson code "$exit_code" \
          '{type: "cli_error", message: $message, output: $stdout, exitCode: $code, executed: $cmd}')"
    exit 0
fi
