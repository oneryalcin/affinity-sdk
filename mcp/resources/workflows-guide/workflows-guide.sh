#!/usr/bin/env bash
# resources/workflows-guide/workflows-guide.sh - Serve workflows skill content
# Reads from .claude-plugin/skills/affinity-mcp-workflows/SKILL.md and strips YAML frontmatter
set -euo pipefail

SKILL_FILE="${MCPBASH_PROJECT_ROOT}/.claude-plugin/skills/affinity-mcp-workflows/SKILL.md"

if [[ ! -f "$SKILL_FILE" ]]; then
    echo "Error: Skill file not found: $SKILL_FILE" >&2
    exit 1
fi

# Strip YAML frontmatter (content between --- markers at start of file)
# Uses awk to skip lines between first --- and second ---
awk '
    BEGIN { in_frontmatter = 0; found_first = 0 }
    /^---$/ {
        if (!found_first) {
            found_first = 1
            in_frontmatter = 1
            next
        } else if (in_frontmatter) {
            in_frontmatter = 0
            next
        }
    }
    !in_frontmatter { print }
' "$SKILL_FILE"
