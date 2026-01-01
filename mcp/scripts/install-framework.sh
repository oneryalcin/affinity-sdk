#!/usr/bin/env bash
# scripts/install-framework.sh - Framework installer with verification
set -euo pipefail

FRAMEWORK_VERSION="${1:-v0.8.3}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Determine install location
if [[ -n "${MCPBASH_HOME:-}" ]]; then
    echo "MCPBASH_HOME is set - using user-managed installation at ${MCPBASH_HOME}"
    echo "Skipping auto-install. Ensure framework >= ${FRAMEWORK_VERSION} is installed."
    exit 0
fi

INSTALL_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/mcp-bash"
LAUNCHER_PATH="${HOME}/.local/bin/mcp-bash"

echo "Installing MCP Bash Framework ${FRAMEWORK_VERSION}..."

# Create install directory
mkdir -p "$(dirname "$INSTALL_DIR")"
mkdir -p "$(dirname "$LAUNCHER_PATH")"

# Clone or update framework
if [[ -d "$INSTALL_DIR/.git" ]]; then
    echo "Updating existing installation..."
    cd "$INSTALL_DIR"
    git fetch origin
    git checkout "${FRAMEWORK_VERSION}"
else
    echo "Fresh installation..."
    rm -rf "$INSTALL_DIR"
    git clone --branch "${FRAMEWORK_VERSION}" --depth 1 https://github.com/yaniv-golan/mcp-bash-framework.git "$INSTALL_DIR"
fi

# Create launcher symlink
ln -sf "${INSTALL_DIR}/bin/mcp-bash" "$LAUNCHER_PATH"

echo "Framework installed at ${INSTALL_DIR}"
echo "Launcher created at ${LAUNCHER_PATH}"

# Verify xaffinity is available
if ! command -v xaffinity &>/dev/null; then
    echo ""
    echo "WARNING: xaffinity CLI not found in PATH"
    echo "Install with: pip install affinity-python-sdk"
fi

echo ""
echo "Installation complete! Run: ./xaffinity-mcp.sh validate"
