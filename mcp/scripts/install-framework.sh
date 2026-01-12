#!/usr/bin/env bash
# scripts/install-framework.sh - Framework installer with verification
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Source version and commit from lockfile
# shellcheck source=../mcp-bash.lock
source "${PROJECT_ROOT}/mcp-bash.lock"

# Allow args to override lockfile values
FRAMEWORK_VERSION="${1:-v${MCPBASH_VERSION}}"
EXPECTED_COMMIT="${2:-${MCPBASH_COMMIT}}"

# Determine install location
if [[ -n "${MCPBASH_HOME:-}" ]]; then
    echo "MCPBASH_HOME is set - refusing to modify user-managed installation" >&2
    echo "Location: ${MCPBASH_HOME}" >&2
    echo "To proceed: unset MCPBASH_HOME or upgrade manually" >&2
    exit 3  # Policy refusal (aligned with mcp-bash 0.9.1)
fi

INSTALL_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/mcp-bash"
LAUNCHER_PATH="${HOME}/.local/bin/mcp-bash"

echo "Installing MCP Bash Framework ${FRAMEWORK_VERSION}..."

# Create install directory
mkdir -p "$(dirname "$INSTALL_DIR")"
mkdir -p "$(dirname "$LAUNCHER_PATH")"

# Clone or update framework using secure fetch pattern
# (avoids downloading untrusted code before verification - see mcp-bash 0.9.1 docs)
FRAMEWORK_REPO="https://github.com/yaniv-golan/mcp-bash-framework.git"

if [[ -d "$INSTALL_DIR/.git" ]]; then
    echo "Updating existing installation..."
    cd "$INSTALL_DIR"
    git -c fetch.fsckobjects=true fetch origin "${FRAMEWORK_VERSION}"
    git checkout FETCH_HEAD
else
    echo "Fresh installation..."
    rm -rf "$INSTALL_DIR"
    mkdir -p "$INSTALL_DIR"
    git init "$INSTALL_DIR"
    git -C "$INSTALL_DIR" remote add origin "$FRAMEWORK_REPO"
    # Secure fetch: only downloads the specific ref, validates git objects
    git -C "$INSTALL_DIR" -c fetch.fsckobjects=true fetch --depth 1 origin "${FRAMEWORK_VERSION}"
    git -C "$INSTALL_DIR" checkout FETCH_HEAD
fi

# Create launcher symlink
ln -sf "${INSTALL_DIR}/bin/mcp-bash" "$LAUNCHER_PATH"

# Verify installed commit matches expected hash (if provided)
if [[ -n "$EXPECTED_COMMIT" ]]; then
    INSTALLED_COMMIT=$(git -C "$INSTALL_DIR" rev-parse HEAD)
    if [[ "$INSTALLED_COMMIT" != "$EXPECTED_COMMIT" ]]; then
        echo "ERROR: Commit hash mismatch!" >&2
        echo "  Expected: $EXPECTED_COMMIT" >&2
        echo "  Got:      $INSTALLED_COMMIT" >&2
        echo "  This may indicate a security issue or version mismatch." >&2
        exit 2
    fi
    echo "Verified: commit hash matches expected value"
fi

echo "Framework installed at ${INSTALL_DIR}"
echo "Launcher created at ${LAUNCHER_PATH}"

# Verify xaffinity is available
if ! command -v xaffinity &>/dev/null; then
    echo ""
    echo "WARNING: xaffinity CLI not found in PATH"
    echo "Install with: pip install affinity-sdk"
fi

echo ""
echo "Installation complete! Run: ./xaffinity-mcp.sh validate"
