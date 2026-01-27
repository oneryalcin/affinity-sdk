#!/usr/bin/env bash
# lib/cli-detect.sh - Runtime CLI detection for restricted PATH environments
#
# MCP hosts may spawn servers with minimal PATH that excludes version manager
# shims. This library detects CLI paths at runtime when $HOME is available.
#
# Based on mcp-bash BEST-PRACTICES.md and CLI-DETECTION-PATTERN.md
#
# Usage:
#   source "${MCPBASH_PROJECT_ROOT}/lib/cli-detect.sh"
#   MYCLI=$(mcp_detect_cli mycli "pip install my-package") || exit 1
#   "${MYCLI}" --version

# Detect a CLI by searching common version manager locations.
#
# Arguments:
#   $1 - CLI name (e.g., "xaffinity", "python", "node")
#   $2 - Install hint shown if not found (optional)
#
# Environment override:
#   ${NAME}_CLI - If set, returns this value (e.g., XAFFINITY_CLI for "xaffinity")
#
# Search order:
#   1. User override via ${NAME}_CLI environment variable
#   2. pyenv shims (~/.pyenv/shims/)
#   3. asdf shims (~/.asdf/shims/)
#   4. mise shims (~/.local/share/mise/shims/)
#   5. rbenv shims (~/.rbenv/shims/)
#   6. goenv shims (~/.goenv/shims/)
#   7. pipx/uv bin (~/.local/bin/)
#   8. cargo bin (~/.cargo/bin/)
#   9. volta bin (~/.volta/bin/)
#   10. nvm versions (~/.nvm/versions/node/*/bin/)
#   11. fnm default (~/.local/share/fnm/aliases/default/bin/)
#   12. Homebrew Apple Silicon (/opt/homebrew/bin/)
#   13. Homebrew Intel (/usr/local/bin/)
#   14. System paths (/usr/bin/, /bin/)
#   15. Current PATH lookup (command -v)
#
# Returns:
#   Prints the full path to the CLI on stdout
#   Exit code 0 if found, 1 if not found (with error message on stderr)
#
mcp_detect_cli() {
    local name="${1:?mcp_detect_cli: CLI name required}"
    local install_hint="${2:-}"

    # Check for user override via ${NAME}_CLI environment variable
    # Use tr for Bash 3.2 compatibility (macOS ships with Bash 3.2)
    local var_name
    var_name="$(printf '%s_CLI' "$name" | tr '[:lower:]-' '[:upper:]_')"

    # Indirect variable expansion
    local override_value=""
    eval "override_value=\"\${${var_name}:-}\""
    if [[ -n "${override_value}" ]]; then
        printf '%s\n' "${override_value}"
        return 0
    fi

    # Build candidate list
    local -a candidates=()

    # Python version managers
    candidates+=("${HOME}/.pyenv/shims/${name}")
    candidates+=("${HOME}/.asdf/shims/${name}")
    candidates+=("${HOME}/.local/share/mise/shims/${name}")

    # Ruby version managers
    candidates+=("${HOME}/.rbenv/shims/${name}")

    # Go version managers
    candidates+=("${HOME}/.goenv/shims/${name}")

    # Python package managers (pipx, uv, pip --user)
    candidates+=("${HOME}/.local/bin/${name}")

    # Rust
    candidates+=("${HOME}/.cargo/bin/${name}")

    # Node.js version managers
    candidates+=("${HOME}/.volta/bin/${name}")
    candidates+=("${HOME}/.local/share/fnm/aliases/default/bin/${name}")

    # nvm: check all installed versions
    local nvm_candidate
    for nvm_candidate in "${HOME}"/.nvm/versions/node/*/bin/"${name}"; do
        [[ -x "${nvm_candidate}" ]] && candidates+=("${nvm_candidate}")
    done

    # Homebrew (check Apple Silicon first, then Intel)
    candidates+=("/opt/homebrew/bin/${name}")
    candidates+=("/usr/local/bin/${name}")

    # macOS Python framework (python.org installer, Homebrew Python)
    local py_version
    for py_version in /Library/Frameworks/Python.framework/Versions/*/bin/"${name}"; do
        [[ -x "${py_version}" ]] && candidates+=("${py_version}")
    done

    # System paths
    candidates+=("/usr/bin/${name}")
    candidates+=("/bin/${name}")

    # Check candidates in order
    # Note: candidates is always populated above, but use safe pattern for Bash 3.2
    local candidate
    for candidate in ${candidates[@]+"${candidates[@]}"}; do
        if [[ -x "${candidate}" ]]; then
            printf '%s\n' "${candidate}"
            return 0
        fi
    done

    # Fall back to PATH lookup
    if command -v "${name}" &>/dev/null; then
        command -v "${name}"
        return 0
    fi

    # Not found - emit actionable error
    {
        printf 'ERROR: %s CLI not found.\n' "${name}"
        if [[ -n "${install_hint}" ]]; then
            printf 'Install with: %s\n' "${install_hint}"
        fi
        printf 'Or set %s=/path/to/%s in your environment.\n' "${var_name}" "${name}"
    } >&2

    return 1
}

# Variant that fails the MCP tool with a proper error response
#
# Usage:
#   MYCLI=$(mcp_detect_cli_or_fail mycli "pip install my-package")
#   # If not found, tool fails with proper MCP error; script exits
#
mcp_detect_cli_or_fail() {
    local name="${1:?}"
    local install_hint="${2:-}"
    local cli_path

    if cli_path=$(mcp_detect_cli "$name" "$install_hint"); then
        printf '%s\n' "${cli_path}"
    else
        # Use mcp_fail if available (tool-sdk.sh sourced), otherwise exit
        if declare -F mcp_fail >/dev/null 2>&1; then
            local msg="${name} CLI not found"
            [[ -n "${install_hint}" ]] && msg+=". Install with: ${install_hint}"
            mcp_fail "${msg}"
        else
            exit 1
        fi
    fi
}
