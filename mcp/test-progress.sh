#!/usr/bin/env bash
# test-progress.sh - Manual test for MCP progress integration
#
# Usage:
#   ./test-progress.sh                    # Run all tests
#   ./test-progress.sh version            # Test version comparison
#   ./test-progress.sh registry           # Test registry lookup
#   ./test-progress.sh dry-run            # Test progress forwarding (dry-run)
#   ./test-progress.sh live               # Test with actual CLI (requires API key)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

pass() { echo -e "${GREEN}✓${NC} $1"; }
fail() { echo -e "${RED}✗${NC} $1"; exit 1; }
skip() { echo -e "${YELLOW}○${NC} $1 (skipped)"; }

# Setup environment
export MCPBASH_PROJECT_ROOT="$SCRIPT_DIR"
# Prefer homebrew jq (system jq on some machines has issues)
if [[ -z "${MCPBASH_JSON_TOOL_BIN:-}" ]]; then
    if [[ -x /opt/homebrew/bin/jq ]]; then
        export MCPBASH_JSON_TOOL_BIN=/opt/homebrew/bin/jq
    elif command -v gojq &>/dev/null; then
        export MCPBASH_JSON_TOOL_BIN=$(command -v gojq)
    else
        export MCPBASH_JSON_TOOL_BIN=jq
    fi
fi
export XAFFINITY_CLI_VERSION="${XAFFINITY_CLI_VERSION:-0.6.10}"

# Source common.sh
source lib/common.sh 2>/dev/null || { fail "Could not source lib/common.sh"; }

test_version() {
    echo "=== Version Comparison Tests ==="

    version_gte "0.6.10" "0.6.10" && pass "0.6.10 >= 0.6.10" || fail "0.6.10 >= 0.6.10"
    version_gte "0.6.11" "0.6.10" && pass "0.6.11 >= 0.6.10" || fail "0.6.11 >= 0.6.10"
    version_gte "0.7.0" "0.6.10" && pass "0.7.0 >= 0.6.10" || fail "0.7.0 >= 0.6.10"
    version_gte "1.0.0" "0.6.10" && pass "1.0.0 >= 0.6.10" || fail "1.0.0 >= 0.6.10"

    # These should fail (return 1)
    version_gte "0.6.9" "0.6.10" && fail "0.6.9 >= 0.6.10 (should fail)" || pass "0.6.9 < 0.6.10 (correctly rejected)"
    version_gte "0.5.0" "0.6.10" && fail "0.5.0 >= 0.6.10 (should fail)" || pass "0.5.0 < 0.6.10 (correctly rejected)"

    echo ""
}

test_registry() {
    echo "=== Registry Lookup Tests ==="

    if [[ ! -f "$REGISTRY_FILE" ]]; then
        fail "Registry not found: $REGISTRY_FILE"
    fi
    pass "Registry exists: $REGISTRY_FILE"

    # Check progress-capable commands
    local capable_commands
    capable_commands=$("$MCPBASH_JSON_TOOL_BIN" -r '[.commands[] | select(.progressCapable == true) | .name] | join(", ")' "$REGISTRY_FILE")

    if [[ -n "$capable_commands" ]]; then
        pass "Progress-capable commands: $capable_commands"
    else
        skip "No progress-capable commands in registry"
    fi

    # Test command_supports_progress function
    export XAFFINITY_CLI_VERSION="0.6.10"
    if command_supports_progress "person files upload"; then
        pass "command_supports_progress('person files upload') = true"
    else
        fail "command_supports_progress('person files upload') should be true"
    fi

    if command_supports_progress "person get"; then
        fail "command_supports_progress('person get') should be false"
    else
        pass "command_supports_progress('person get') = false (not progress-capable)"
    fi

    # Test with old CLI version
    export XAFFINITY_CLI_VERSION="0.6.9"
    if command_supports_progress "person files upload"; then
        fail "command_supports_progress with old CLI should be false"
    else
        pass "command_supports_progress('person files upload', CLI=0.6.9) = false (old CLI)"
    fi

    echo ""
}

test_dry_run() {
    echo "=== Dry-Run Progress Test ==="

    # Create a mock CLI that emits progress
    local mock_cli
    mock_cli=$(mktemp)
    cat > "$mock_cli" << 'MOCK'
#!/bin/bash
# Mock CLI that emits progress to stderr
echo '{"type":"progress","progress":0,"message":"Starting..."}' >&2
sleep 0.1
echo '{"type":"progress","progress":50,"message":"Halfway..."}' >&2
sleep 0.1
echo '{"type":"progress","progress":100,"message":"Complete"}' >&2
echo '{"data":{"result":"success"}}'
MOCK
    chmod +x "$mock_cli"

    echo "Mock CLI created at: $mock_cli"
    echo "Testing progress pattern matching..."

    # Test the pattern
    local pattern='^\{.*"type"[[:space:]]*:[[:space:]]*"progress"'
    local test_line='{"type":"progress","progress":50,"message":"test"}'

    if [[ "$test_line" =~ $pattern ]]; then
        pass "Progress pattern matches: $test_line"
    else
        fail "Progress pattern should match: $test_line"
    fi

    # Test non-progress line
    local data_line='{"data":{"result":"success"}}'
    if [[ "$data_line" =~ $pattern ]]; then
        fail "Progress pattern should NOT match data: $data_line"
    else
        pass "Progress pattern correctly rejects: $data_line"
    fi

    # Run mock CLI and capture progress
    echo ""
    echo "Running mock CLI with progress capture..."
    local output stderr_output
    stderr_output=$("$mock_cli" 2>&1 >/dev/null)

    echo "Progress output:"
    echo "$stderr_output" | while read -r line; do
        if [[ "$line" =~ $pattern ]]; then
            echo "  [PROGRESS] $line"
        fi
    done

    rm -f "$mock_cli"
    pass "Dry-run test complete"
    echo ""
}

test_live() {
    echo "=== Live CLI Test ==="

    # Allow overriding CLI command for testing dev version
    # Usage: XAFFINITY_CMD="python -m affinity.cli" ./test-progress.sh live
    local cli_cmd="${XAFFINITY_CMD:-xaffinity}"

    if [[ "$cli_cmd" == "xaffinity" ]] && ! command -v xaffinity &>/dev/null; then
        skip "xaffinity CLI not found"
        return
    fi

    # Check if running dev version (from parent directory)
    local project_root
    project_root=$(dirname "$SCRIPT_DIR")
    local pyproject_version
    pyproject_version=$(grep '^version' "$project_root/pyproject.toml" 2>/dev/null | head -1 | sed 's/.*"\(.*\)".*/\1/')

    echo "Testing with CLI: $cli_cmd"
    [[ -n "$pyproject_version" ]] && echo "pyproject.toml version: $pyproject_version"

    # Get actual CLI version
    local cli_version
    cli_version=$($cli_cmd version --output json 2>/dev/null | "$MCPBASH_JSON_TOOL_BIN" -r '.data.version // "unknown"')
    echo "CLI reports version: $cli_version"

    # Warn if versions don't match (dev version not installed)
    if [[ -n "$pyproject_version" && "$cli_version" != "$pyproject_version" ]]; then
        echo ""
        echo -e "${YELLOW}⚠ Version mismatch: CLI=$cli_version, pyproject.toml=$pyproject_version${NC}"
        echo "  To test with dev version, run: pip install -e $project_root"
        echo ""
    fi

    if version_gte "$cli_version" "$PROGRESS_MIN_CLI_VERSION"; then
        pass "CLI version $cli_version supports progress"
    else
        skip "CLI version $cli_version < $PROGRESS_MIN_CLI_VERSION (progress not supported)"
        echo ""
        echo "To test progress with dev version:"
        echo "  1. pip install -e $project_root"
        echo "  2. ./test-progress.sh live"
        return
    fi

    # Check if API key is configured
    if ! $cli_cmd config check-key --json &>/dev/null; then
        skip "Affinity API key not configured"
        return
    fi

    # Test progress output (non-TTY mode)
    echo ""
    echo "Testing CLI JSON progress output (non-TTY simulation)..."

    # Create a simple test that captures stderr
    local test_output
    test_output=$($cli_cmd version --output json 2>&1)
    echo "CLI output: $(echo "$test_output" | head -1)"
    pass "CLI executes successfully"

    # Test execute-read-command tool
    echo ""
    echo "Testing execute-read-command tool..."

    if command -v mcp-bash &>/dev/null; then
        echo "Running: mcp-bash run-tool execute-read-command --args '{\"command\":\"version\",\"argv\":[]}'"
        mcp-bash run-tool execute-read-command \
            --args '{"command":"version","argv":[]}' \
            --project-root "$SCRIPT_DIR" \
            2>&1 | head -20
        pass "execute-read-command tool works"
    else
        skip "mcp-bash not found in PATH"
    fi

    echo ""
}

# Main
case "${1:-all}" in
    version)  test_version ;;
    registry) test_registry ;;
    dry-run)  test_dry_run ;;
    live)     test_live ;;
    all)
        test_version
        test_registry
        test_dry_run
        test_live
        echo "=== All tests complete ==="
        ;;
    *)
        echo "Usage: $0 [version|registry|dry-run|live|all]"
        exit 1
        ;;
esac
