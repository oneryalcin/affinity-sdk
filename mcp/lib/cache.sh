#!/usr/bin/env bash
# lib/cache.sh - Session cache utilities for Affinity MCP tools

# Check if session cache is available
cache_enabled() {
    [[ -n "${AFFINITY_SESSION_CACHE:-}" ]] && [[ -d "${AFFINITY_SESSION_CACHE}" ]]
}

# Get workflow config from cache
get_workflow_config_cached() {
    local list_id="$1"
    local cache_key="workflow_config_${list_id}"

    if cache_enabled; then
        local cache_file="${AFFINITY_SESSION_CACHE}/${cache_key}.json"
        if [[ -f "$cache_file" ]]; then
            local age=$(($(date +%s) - $(stat -f %m "$cache_file" 2>/dev/null || stat -c %Y "$cache_file")))
            if [[ $age -lt ${AFFINITY_SESSION_CACHE_TTL:-600} ]]; then
                cat "$cache_file"
                return 0
            fi
        fi
    fi
    return 1
}

# Store workflow config in cache
set_workflow_config_cached() {
    local list_id="$1"
    local data="$2"

    if cache_enabled; then
        local cache_file="${AFFINITY_SESSION_CACHE}/workflow_config_${list_id}.json"
        echo "$data" > "${cache_file}.tmp" && mv "${cache_file}.tmp" "$cache_file"
    fi
}

# Invalidate cache entries by prefix
invalidate_cache_prefix() {
    local prefix="$1"
    if cache_enabled; then
        rm -f "${AFFINITY_SESSION_CACHE}/${prefix}"*.json 2>/dev/null || true
    fi
}

# Get current user's person ID (cached for frequent interaction logging)
get_me_person_id_cached() {
    local cache_key="me_person_id"

    if cache_enabled; then
        local cache_file="${AFFINITY_SESSION_CACHE}/${cache_key}.json"
        if [[ -f "$cache_file" ]]; then
            local age=$(($(date +%s) - $(stat -f %m "$cache_file" 2>/dev/null || stat -c %Y "$cache_file")))
            if [[ $age -lt ${AFFINITY_SESSION_CACHE_TTL:-600} ]]; then
                jq_tool -r '.personId // empty' "$cache_file"
                return 0
            fi
        fi
    fi
    return 1
}

# Cache current user's person ID
set_me_person_id_cached() {
    local person_id="$1"
    if cache_enabled && [[ -n "$person_id" ]]; then
        echo "{\"personId\": $person_id}" > "${AFFINITY_SESSION_CACHE}/me_person_id.json"
    fi
}

# Get person internal/external status (cached to avoid repeated lookups)
get_person_internal_status_cached() {
    local person_id="$1"
    local cache_key="person_internal_${person_id}"

    if cache_enabled; then
        local cache_file="${AFFINITY_SESSION_CACHE}/${cache_key}.json"
        if [[ -f "$cache_file" ]]; then
            local age=$(($(date +%s) - $(stat -f %m "$cache_file" 2>/dev/null || stat -c %Y "$cache_file")))
            if [[ $age -lt ${AFFINITY_SESSION_CACHE_TTL:-600} ]]; then
                cat "$cache_file"
                return 0
            fi
        fi
    fi
    return 1
}

# Cache person internal/external status
set_person_internal_status_cached() {
    local person_id="$1"
    local is_internal="$2"  # "true" or "false"
    if cache_enabled; then
        echo "{\"isInternal\": $is_internal}" > "${AFFINITY_SESSION_CACHE}/person_internal_${person_id}.json"
    fi
}

# Generic cache get
cache_get() {
    local cache_key="$1"

    if cache_enabled; then
        local cache_file="${AFFINITY_SESSION_CACHE}/${cache_key}.json"
        if [[ -f "$cache_file" ]]; then
            local age=$(($(date +%s) - $(stat -f %m "$cache_file" 2>/dev/null || stat -c %Y "$cache_file")))
            if [[ $age -lt ${AFFINITY_SESSION_CACHE_TTL:-600} ]]; then
                cat "$cache_file"
                return 0
            fi
        fi
    fi
    return 1
}

# Generic cache set
cache_set() {
    local cache_key="$1"
    local data="$2"

    if cache_enabled; then
        local cache_file="${AFFINITY_SESSION_CACHE}/${cache_key}.json"
        echo "$data" > "${cache_file}.tmp" && mv "${cache_file}.tmp" "$cache_file"
    fi
}
