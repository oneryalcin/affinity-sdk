#!/usr/bin/env bash
# tools/execute-write-command/tool.sh - Execute a write CLI command (create, update, delete)
set -euo pipefail

source "${MCP_SDK:?}/tool-sdk.sh"
source "${MCPBASH_PROJECT_ROOT}/lib/common.sh"
source "${MCPBASH_PROJECT_ROOT}/lib/cli-gateway.sh"

# Validate registry early
validate_registry || exit 0

# Parse arguments using mcp-bash SDK
command="$(mcp_args_require '.command' 'Command is required')"
argv_json="$(mcp_args_get '.argv // []')"
confirm="$(mcp_args_get '.confirm // false')"
dry_run="$(mcp_args_get '.dryRun // false')"

# Log tool invocation
xaffinity_log_debug "execute-write-command" "command='$command' confirm=$confirm dryRun=$dry_run"

# Track start time for latency metrics
start_time_ms=$(($(date +%s%3N 2>/dev/null || echo 0)))

# Validate command is in registry with category=write
validate_command "$command" "write" || exit 0

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

# Block destructive commands entirely if policy disables them
if [[ "${AFFINITY_MCP_DISABLE_DESTRUCTIVE:-}" == "1" ]] && is_destructive "$command"; then
    mcp_result_error '{"type": "destructive_disabled", "message": "Destructive commands are disabled by policy (AFFINITY_MCP_DISABLE_DESTRUCTIVE=1)"}'
    exit 0
fi

# Handle destructive operations with layered confirmation
if is_destructive "$command"; then
    # Check if --yes already in argv (user shouldn't provide it directly)
    has_yes=false
    for arg in "${argv[@]}"; do
        [[ "$arg" == "--yes" || "$arg" == "-y" ]] && has_yes=true && break
    done
    if [[ "$has_yes" == "true" ]]; then
        mcp_result_error '{"type": "validation_error", "message": "--yes flag not allowed in argv; use confirm parameter instead"}'
        exit 0
    fi

    # Verify command supports --yes flag before we try to append it
    supports_yes=$(jq_tool -r --arg cmd "$command" \
        '.commands[] | select(.name == $cmd) | .parameters["--yes"] // empty' \
        "$REGISTRY_FILE")
    if [[ -z "$supports_yes" ]]; then
        mcp_result_error "$(jq_tool -n --arg cmd "$command" \
            '{type: "internal_error", message: ("Destructive command " + $cmd + " does not support --yes flag; registry may be out of sync")}')"
        exit 0
    fi

    if [[ "$confirm" == "true" ]]; then
        argv+=("--yes")
    elif [[ "${MCP_ELICIT_SUPPORTED:-0}" == "1" ]]; then
        response=$(mcp_elicit_confirm "Confirm: $command - This action cannot be undone.")
        action=$(printf '%s' "$response" | jq_tool -r '.action // "decline"')
        if [[ "$action" == "accept" ]]; then
            argv+=("--yes")
        else
            # User declined - return cancelled (not an error)
            mcp_result_success '{"result": null, "cancelled": true}'
            exit 0
        fi
    else
        # Build example showing how to confirm
        mcp_result_error "$(jq_tool -n \
            --arg cmd "$command" \
            --argjson argv "$argv_json" \
            '{
                type: "confirmation_required",
                message: "Destructive command requires confirm=true",
                hint: "Add \"confirm\": true to your request to proceed",
                example: {command: $cmd, argv: $argv, confirm: true}
            }')"
        exit 0
    fi
fi

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

# Report progress
mcp_progress 0 "Executing: ${command}"

# Execute CLI (no retry for write commands to avoid duplicate side effects)
set +e
"${cmd_args[@]}" >"$stdout_file" 2>"$stderr_file"
exit_code=$?
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
end_time_ms=$(($(date +%s%3N 2>/dev/null || echo 0)))
latency_ms=$((end_time_ms - start_time_ms))

# Log result and metrics
xaffinity_log_debug "execute-write-command" "exit_code=$exit_code output_bytes=${#stdout_content} latency_ms=$latency_ms"
log_metric "cli_command_latency_ms" "$latency_ms" "command=$command" "status=$([[ $exit_code -eq 0 ]] && echo 'success' || echo 'error')" "category=write"
log_metric "cli_command_output_bytes" "${#stdout_content}" "command=$command"

# Report completion progress
mcp_progress 100 "Complete"

if [[ $exit_code -eq 0 ]]; then
    # Validate stdout is valid JSON before using --argjson
    if mcp_is_valid_json "$stdout_content"; then
        mcp_result_success "$(jq_tool -n --argjson result "$stdout_content" \
              --argjson cmd "$cmd_json" \
              '{result: $result, executed: $cmd}')"
    else
        mcp_result_error "$(jq_tool -n --arg stdout "$stdout_content" \
              --argjson cmd "$cmd_json" \
              '{type: "invalid_json_output", message: "CLI returned non-JSON output", output: $stdout, executed: $cmd}')"
    fi
else
    mcp_result_error "$(jq_tool -n --arg stderr "$stderr_content" \
          --arg stdout "$stdout_content" \
          --argjson cmd "$cmd_json" \
          --argjson code "$exit_code" \
          '{type: "cli_error", message: $stderr, output: $stdout, exitCode: $code, executed: $cmd}')"
fi
