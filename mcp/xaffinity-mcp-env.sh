#!/usr/bin/env bash
# xaffinity-mcp-env.sh - Fallback launcher that sources shell profiles
# Use this when "command not found" errors occur from GUI apps

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Source login shell profile to get PATH (xaffinity, etc.)
if [[ -z "${AFFINITY_MCP_ENV_SOURCED:-}" ]]; then
    export AFFINITY_MCP_ENV_SOURCED=1

    # Silence profile output to preserve stdio
    if [[ "${AFFINITY_MCP_ENV_SILENCE_PROFILE:-1}" == "1" ]]; then
        exec 3>&1 4>&2 1>/dev/null 2>&1
    fi

    # Source appropriate profiles (both login and interactive for full PATH setup)
    # zsh: .zprofile (login) + .zshrc (interactive, often has pyenv/nvm/etc.)
    # bash: .bash_profile or .profile
    if [[ -f "$HOME/.zprofile" ]]; then
        source "$HOME/.zprofile" 2>/dev/null || true
    fi
    if [[ -f "$HOME/.zshrc" ]]; then
        source "$HOME/.zshrc" 2>/dev/null || true
    elif [[ -f "$HOME/.bash_profile" ]]; then
        source "$HOME/.bash_profile" 2>/dev/null || true
    elif [[ -f "$HOME/.profile" ]]; then
        source "$HOME/.profile" 2>/dev/null || true
    fi

    # Restore output
    if [[ "${AFFINITY_MCP_ENV_SILENCE_PROFILE:-1}" == "1" ]]; then
        exec 1>&3 2>&4 3>&- 4>&-
    fi
fi

# Delegate to main launcher
exec "${SCRIPT_DIR}/xaffinity-mcp.sh" "$@"
