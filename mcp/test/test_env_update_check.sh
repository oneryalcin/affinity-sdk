#!/usr/bin/env bash
# test_env_update_check.sh - Integration tests for env.sh update check functionality
#
# Usage: ./test_env_update_check.sh
#
# These tests verify the update check behavior in env.sh using a mock xaffinity CLI.

set -euo pipefail

# Test directory setup
TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$TEST_DIR/.." && pwd)"
ENV_SH="$PROJECT_ROOT/server.d/env.sh"

# Temporary directory for test artifacts
TMPDIR_BASE="${TMPDIR:-/tmp}/test_env_update_check_$$"
mkdir -p "$TMPDIR_BASE"
trap 'rm -rf "$TMPDIR_BASE"' EXIT

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

# Test counters
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

# ==============================================================================
# Test Utilities
# ==============================================================================

log_test() {
    echo -e "${YELLOW}TEST:${NC} $1"
}

log_pass() {
    echo -e "${GREEN}PASS:${NC} $1"
    ((TESTS_PASSED++)) || true
}

log_fail() {
    echo -e "${RED}FAIL:${NC} $1"
    ((TESTS_FAILED++)) || true
}

# Create a mock xaffinity CLI that returns controlled responses
create_mock_cli() {
    local mock_dir="$1"
    local response="$2"
    local background_behavior="${3:-success}"  # success or fail

    mkdir -p "$mock_dir"
    cat > "$mock_dir/xaffinity" << MOCKEOF
#!/usr/bin/env bash
# Handle: xaffinity --json config update-check --status
if [[ "\$1" == "--json" ]] && [[ "\$2" == "config" ]] && [[ "\$3" == "update-check" ]] && [[ "\$4" == "--status" ]]; then
    echo '$response'
    exit 0
fi
# Handle: xaffinity config update-check --background (no --json)
if [[ "\$1" == "config" ]] && [[ "\$2" == "update-check" ]] && [[ "\$3" == "--background" ]]; then
    echo "background_called" >> "$mock_dir/calls.log"
    if [[ "$background_behavior" == "fail" ]]; then
        exit 1
    fi
    exit 0
fi
# Log any other calls
echo "\$*" >> "$mock_dir/calls.log"
exit 0
MOCKEOF
    chmod +x "$mock_dir/xaffinity"
}

# Run env.sh in isolated environment and capture output
run_env_sh_isolated() {
    local mock_dir="$1"
    local test_id="$2"
    local extra_env="${3:-}"

    local test_state_dir="$TMPDIR_BASE/state_$test_id"
    mkdir -p "$test_state_dir"

    # Run in subshell with controlled environment
    bash -c "
        export PATH=\"$mock_dir:\$PATH\"
        export XDG_STATE_HOME=\"$test_state_dir\"
        export MCPBASH_JSON_TOOL=\"jq\"
        unset _XAFFINITY_UPDATE_CHECK_RAN
        $extra_env
        source \"$ENV_SH\"
    " 2>&1
}

# ==============================================================================
# Tests
# ==============================================================================

test_warning_shown_when_update_available() {
    log_test "Warning shown when update available"
    ((TESTS_RUN++)) || true

    local mock_dir="$TMPDIR_BASE/mock_warning"
    create_mock_cli "$mock_dir" '{"data":{"update_check_enabled":true,"update_notify_mode":"interactive","update_available":true,"current_version":"1.0.0","latest_version":"2.0.0","upgrade_command":"pip install --upgrade test","cache_stale":false,"state_dir":"'"$TMPDIR_BASE/state"'"}}'

    local output
    output=$(run_env_sh_isolated "$mock_dir" "warning")

    if echo "$output" | grep -q "CLI update available: 1.0.0"; then
        log_pass "Warning shown correctly"
    else
        log_fail "Warning not shown. Output: $output"
    fi
}

test_warning_shown_every_startup() {
    log_test "Warning shown on EVERY startup (not throttled)"
    ((TESTS_RUN++)) || true

    local mock_dir="$TMPDIR_BASE/mock_every"
    create_mock_cli "$mock_dir" '{"data":{"update_check_enabled":true,"update_notify_mode":"interactive","update_available":true,"current_version":"1.0.0","latest_version":"2.0.0","upgrade_command":"pip test","cache_stale":false,"state_dir":"'"$TMPDIR_BASE/state_every"'"}}'

    local output1 output2
    output1=$(run_env_sh_isolated "$mock_dir" "every1")
    output2=$(run_env_sh_isolated "$mock_dir" "every2")

    local has1 has2
    has1=$(echo "$output1" | grep -c "CLI update available" || true)
    has2=$(echo "$output2" | grep -c "CLI update available" || true)

    if [[ "$has1" -ge 1 ]] && [[ "$has2" -ge 1 ]]; then
        log_pass "Warning shown on both startups"
    else
        log_fail "Warning not shown on both startups. First: $has1, Second: $has2"
    fi
}

test_no_warning_when_notify_mode_never() {
    log_test "No warning when update_notify_mode=never"
    ((TESTS_RUN++)) || true

    local mock_dir="$TMPDIR_BASE/mock_never"
    create_mock_cli "$mock_dir" '{"data":{"update_check_enabled":true,"update_notify_mode":"never","update_available":true,"current_version":"1.0.0","latest_version":"2.0.0","cache_stale":true,"state_dir":"'"$TMPDIR_BASE/state_never"'"}}'

    local output
    output=$(run_env_sh_isolated "$mock_dir" "never")

    if echo "$output" | grep -q "CLI update available"; then
        log_fail "Warning shown when notify_mode=never. Output: $output"
    else
        log_pass "Warning suppressed correctly"
    fi
}

test_background_spawn_when_cache_stale() {
    log_test "Background spawn triggered when cache stale"
    ((TESTS_RUN++)) || true

    local mock_dir="$TMPDIR_BASE/mock_stale"
    rm -f "$mock_dir/calls.log"
    create_mock_cli "$mock_dir" '{"data":{"update_check_enabled":true,"update_notify_mode":"interactive","update_available":false,"cache_stale":true,"state_dir":"'"$TMPDIR_BASE/state_stale"'"}}'

    run_env_sh_isolated "$mock_dir" "stale" > /dev/null

    if [[ -f "$mock_dir/calls.log" ]] && grep -q "background_called" "$mock_dir/calls.log"; then
        log_pass "Background spawn triggered"
    else
        log_fail "Background spawn not triggered"
    fi
}

test_no_spawn_when_cache_fresh() {
    log_test "No background spawn when cache fresh"
    ((TESTS_RUN++)) || true

    local mock_dir="$TMPDIR_BASE/mock_fresh"
    rm -f "$mock_dir/calls.log"
    create_mock_cli "$mock_dir" '{"data":{"update_check_enabled":true,"update_notify_mode":"interactive","update_available":false,"cache_stale":false,"state_dir":"'"$TMPDIR_BASE/state_fresh"'"}}'

    run_env_sh_isolated "$mock_dir" "fresh" > /dev/null

    if [[ -f "$mock_dir/calls.log" ]] && grep -q "background_called" "$mock_dir/calls.log"; then
        log_fail "Background spawn triggered when cache fresh"
    else
        log_pass "Background spawn correctly skipped"
    fi
}

test_optout_env_var() {
    log_test "Opt-out via XAFFINITY_NO_UPDATE_CHECK=1"
    ((TESTS_RUN++)) || true

    local mock_dir="$TMPDIR_BASE/mock_optout"
    rm -f "$mock_dir/calls.log"
    create_mock_cli "$mock_dir" '{"data":{"update_check_enabled":true,"update_notify_mode":"interactive","update_available":true,"current_version":"1.0.0","latest_version":"2.0.0","cache_stale":true,"state_dir":"'"$TMPDIR_BASE/state_optout"'"}}'

    local output
    output=$(run_env_sh_isolated "$mock_dir" "optout" "export XAFFINITY_NO_UPDATE_CHECK=1")

    # Should not show warning
    if echo "$output" | grep -q "CLI update available"; then
        log_fail "Warning shown despite opt-out"
        return
    fi

    # Should not have any calls logged (CLI not invoked)
    if [[ -f "$mock_dir/calls.log" ]]; then
        log_fail "CLI called despite opt-out"
    else
        log_pass "Opt-out respected"
    fi
}

test_optout_config_disabled() {
    log_test "Opt-out via config (update_check_enabled=false)"
    ((TESTS_RUN++)) || true

    local mock_dir="$TMPDIR_BASE/mock_config"
    rm -f "$mock_dir/calls.log"
    create_mock_cli "$mock_dir" '{"data":{"update_check_enabled":false,"update_notify_mode":"interactive","update_available":true,"current_version":"1.0.0","latest_version":"2.0.0","cache_stale":true,"state_dir":"'"$TMPDIR_BASE/state_config"'"}}'

    local output
    output=$(run_env_sh_isolated "$mock_dir" "config")

    if echo "$output" | grep -q "CLI update available"; then
        log_fail "Warning shown despite config opt-out"
    else
        log_pass "Config opt-out respected"
    fi
}

test_no_json_tool_skips_check() {
    log_test "No JSON tool available skips check"
    ((TESTS_RUN++)) || true

    local mock_dir="$TMPDIR_BASE/mock_nojson"
    rm -f "$mock_dir/calls.log"
    create_mock_cli "$mock_dir" '{"data":{"update_check_enabled":true,"update_available":true}}'

    # Run without JSON tool
    local output
    output=$(bash -c "
        export PATH=\"$mock_dir\"
        unset MCPBASH_JSON_TOOL
        unset _XAFFINITY_UPDATE_CHECK_RAN
        export XDG_STATE_HOME=\"$TMPDIR_BASE/state_nojson\"
        mkdir -p \"$TMPDIR_BASE/state_nojson\"
        source \"$ENV_SH\"
    " 2>&1) || true

    # CLI should not have been called
    if [[ -f "$mock_dir/calls.log" ]]; then
        log_fail "CLI called without JSON tool"
    else
        log_pass "Check skipped without JSON tool"
    fi
}

test_throttle_prevents_duplicate_spawn() {
    log_test "Throttle prevents duplicate background spawn within 24h"
    ((TESTS_RUN++)) || true

    local mock_dir="$TMPDIR_BASE/mock_throttle"
    local state_dir="$TMPDIR_BASE/state_throttle"
    mkdir -p "$state_dir"
    rm -f "$mock_dir/calls.log"

    create_mock_cli "$mock_dir" '{"data":{"update_check_enabled":true,"update_notify_mode":"interactive","update_available":false,"cache_stale":true,"state_dir":"'"$state_dir"'"}}'

    # First run
    bash -c "
        export PATH=\"$mock_dir:\$PATH\"
        export MCPBASH_JSON_TOOL=\"jq\"
        export XDG_STATE_HOME=\"$state_dir\"
        unset _XAFFINITY_UPDATE_CHECK_RAN
        source \"$ENV_SH\"
    " 2>/dev/null

    local first_count=0
    if [[ -f "$mock_dir/calls.log" ]]; then
        first_count=$(grep -c "background_called" "$mock_dir/calls.log" || true)
    fi

    # Second run (same state dir, so throttle file exists)
    bash -c "
        export PATH=\"$mock_dir:\$PATH\"
        export MCPBASH_JSON_TOOL=\"jq\"
        export XDG_STATE_HOME=\"$state_dir\"
        unset _XAFFINITY_UPDATE_CHECK_RAN
        source \"$ENV_SH\"
    " 2>/dev/null

    local second_count=0
    if [[ -f "$mock_dir/calls.log" ]]; then
        second_count=$(grep -c "background_called" "$mock_dir/calls.log" || true)
    fi

    if [[ "$first_count" -eq 1 ]] && [[ "$second_count" -eq 1 ]]; then
        log_pass "Throttle prevented duplicate spawn"
    else
        log_fail "Throttle failed. First calls: $first_count, Total after second: $second_count"
    fi
}

test_json_flag_placement() {
    log_test "JSON invocation uses correct flag placement"
    ((TESTS_RUN++)) || true

    local mock_dir="$TMPDIR_BASE/mock_json"
    mkdir -p "$mock_dir"

    # Create mock that logs exact arguments
    cat > "$mock_dir/xaffinity" << 'MOCKEOF'
#!/usr/bin/env bash
echo "$*" >> /tmp/xaffinity_args_test.log
if [[ "$1" == "--json" ]]; then
    echo '{"data":{"update_check_enabled":true,"update_notify_mode":"interactive","update_available":false,"cache_stale":false,"state_dir":"/tmp"}}'
fi
exit 0
MOCKEOF
    chmod +x "$mock_dir/xaffinity"

    rm -f /tmp/xaffinity_args_test.log
    run_env_sh_isolated "$mock_dir" "json" > /dev/null

    if [[ -f /tmp/xaffinity_args_test.log ]]; then
        local args
        args=$(cat /tmp/xaffinity_args_test.log)
        rm -f /tmp/xaffinity_args_test.log
        if echo "$args" | grep -q "^--json config update-check"; then
            log_pass "JSON flag placed correctly before subcommand"
        else
            log_fail "Wrong flag placement: $args"
        fi
    else
        log_fail "No CLI invocation recorded"
    fi
}

test_notify_never_still_spawns_background() {
    log_test "notify_mode=never suppresses warning but spawns background"
    ((TESTS_RUN++)) || true

    local mock_dir="$TMPDIR_BASE/mock_never_spawn"
    rm -f "$mock_dir/calls.log"
    create_mock_cli "$mock_dir" '{"data":{"update_check_enabled":true,"update_notify_mode":"never","update_available":true,"current_version":"1.0.0","latest_version":"2.0.0","cache_stale":true,"state_dir":"'"$TMPDIR_BASE/state_never_spawn"'"}}'

    local output
    output=$(run_env_sh_isolated "$mock_dir" "never_spawn")

    # Should NOT show warning
    local has_warning=0
    if echo "$output" | grep -q "CLI update available"; then
        has_warning=1
    fi

    # Should spawn background
    local has_spawn=0
    if [[ -f "$mock_dir/calls.log" ]] && grep -q "background_called" "$mock_dir/calls.log"; then
        has_spawn=1
    fi

    if [[ "$has_warning" -eq 0 ]] && [[ "$has_spawn" -eq 1 ]]; then
        log_pass "Warning suppressed but background spawned"
    else
        log_fail "Warning shown: $has_warning, Spawn triggered: $has_spawn"
    fi
}

# ==============================================================================
# Main
# ==============================================================================

main() {
    echo "=============================================="
    echo "env.sh Update Check Integration Tests"
    echo "=============================================="
    echo ""

    # Check prerequisites
    if ! command -v jq &>/dev/null; then
        echo "ERROR: jq is required for these tests"
        exit 1
    fi

    if [[ ! -f "$ENV_SH" ]]; then
        echo "ERROR: env.sh not found at $ENV_SH"
        exit 1
    fi

    # Run tests
    test_warning_shown_when_update_available
    test_warning_shown_every_startup
    test_no_warning_when_notify_mode_never
    test_background_spawn_when_cache_stale
    test_no_spawn_when_cache_fresh
    test_optout_env_var
    test_optout_config_disabled
    test_no_json_tool_skips_check
    test_throttle_prevents_duplicate_spawn
    test_json_flag_placement
    test_notify_never_still_spawns_background

    # Summary
    echo ""
    echo "=============================================="
    echo "Results: $TESTS_PASSED/$TESTS_RUN passed, $TESTS_FAILED failed"
    echo "=============================================="

    if [[ "$TESTS_FAILED" -gt 0 ]]; then
        exit 1
    fi
}

main "$@"
