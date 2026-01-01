# Claude Integrations

The Affinity SDK provides three [Claude Code](https://docs.anthropic.com/en/docs/claude-code) plugins for different use cases:

| Plugin | Best For | Key Feature |
|--------|----------|-------------|
| **sdk** | Python developers | Type-safe SDK patterns |
| **cli** | CLI power users | `/affinity-help` quick reference |
| **mcp** | Agentic workflows | Meeting prep, pipeline management |

All plugins are installed from the `xaffinity` marketplace.

## Choose Your Plugin

- **"I want to write Python scripts"** - Install `sdk`
- **"I want Claude to run CLI commands"** - Install `cli`
- **"I want agentic workflows (meeting prep, logging calls)"** - Install `mcp`

You can install multiple plugins. They complement each other.

## Installation

Add the marketplace (one-time):

```bash
/plugin marketplace add yaniv-golan/affinity-sdk
```

Install the plugin(s) you need:

```bash
# For Python SDK development
/plugin install sdk@xaffinity

# For CLI usage + /affinity-help command
/plugin install cli@xaffinity

# For agentic workflows (MCP tools + prompts)
/plugin install mcp@xaffinity
```

---

## SDK Plugin

Teaches Claude the correct patterns for writing Python scripts with the Affinity SDK.

### What Claude learns

**Use typed IDs (not raw integers)**

```python
from affinity.types import PersonId, CompanyId

client.persons.get(PersonId(123))     # Correct
client.persons.get(123)               # Wrong - type error
```

**Use context managers**

```python
with Affinity.from_env() as client:   # Correct
    ...

client = Affinity.from_env()          # May leak resources
```

**Use read-only mode by default**

```python
from affinity.policies import Policies, WritePolicy

# Default: read-only (prevents accidental data modification)
with Affinity.from_env(policies=Policies(write=WritePolicy.DENY)) as client:
    ...
```

**Filters only work on custom fields**

```python
from affinity import F

# Works - custom fields
client.persons.list(filter=F.field("Department").equals("Sales"))

# Won't work - built-in properties like firstName, lastName, domain, etc.
```

### Example prompts

- "Write a script to export all companies to CSV"
- "How do I filter persons by a custom field?"
- "Get all entries from my Deal Pipeline list"

---

## CLI Plugin

Teaches Claude the correct patterns for running `xaffinity` CLI commands.

### /affinity-help command

Run `/affinity-help` in Claude Code for a quick reference of CLI patterns.

### What Claude learns

- Always use `--readonly` by default
- Use `--json` for structured, parseable output
- Run `xaffinity config check-key --json` to verify API key configuration
- Use `--all` with caution (can be slow for large datasets)
- Filters only work on custom fields

### Example prompts

- "Export all my contacts to CSV"
- "Find the company with domain acme.com"
- "Show me all entries in my Deal Pipeline"

---

## MCP Plugin

Provides MCP tools for agentic workflows. Best for:

- Meeting preparation
- Logging calls and updating pipelines
- Finding warm introductions
- Pipeline reviews

### Available Tools (14)

| Tool | Purpose |
|------|---------|
| `find-entities` | Search persons, companies, opportunities |
| `find-lists` | Find Affinity lists by name |
| `get-entity-dossier` | Full context: details, interactions, notes, relationships |
| `get-list-workflow-config` | Get workflow config (statuses, fields) for a list |
| `get-workflow-view` | Get items from a saved workflow view |
| `resolve-workflow-item` | Resolve entity to list entry ID |
| `set-workflow-status` | Update pipeline stage **(write)** |
| `update-workflow-fields` | Update multiple fields **(write)** |
| `get-relationship-insights` | Relationship strength, warm intro paths |
| `get-status-timeline` | Status change history |
| `get-interactions` | Interaction history for entity |
| `add-note` | Add note to entity **(write)** |
| `log-interaction` | Log calls, meetings, emails **(write)** |
| `read-xaffinity-resource` | Access dynamic resources |

### Guided Workflows (8 Prompts)

| Prompt | Use Case |
|--------|----------|
| `prepare-briefing` | Before a meeting - get full context on a person/company |
| `pipeline-review` | Weekly pipeline review |
| `warm-intro` | Find connection paths to someone |
| `interaction-brief` | Get interaction history summary |
| `log-interaction-and-update-workflow` | After a call - log and update pipeline **(write)** |
| `change-status` | Move deal to new stage **(write)** |
| `log-call` | Quick phone call logging **(write)** |
| `log-message` | Quick chat/text logging **(write)** |

### Example: Meeting Prep

Ask Claude: "Prepare me for my meeting with John Smith at Acme Corp"

Claude will use the `prepare-briefing` prompt to:

1. Find the person/company
2. Get relationship strength
3. Summarize recent interactions
4. List notes and context

---

## Updating Plugins

```bash
/plugin marketplace update
/plugin update sdk@xaffinity
/plugin update cli@xaffinity
/plugin update mcp@xaffinity
```

## Uninstalling

```bash
/plugin uninstall sdk@xaffinity
/plugin uninstall cli@xaffinity
/plugin uninstall mcp@xaffinity
```
