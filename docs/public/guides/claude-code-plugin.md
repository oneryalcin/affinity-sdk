# Claude Code Plugin

The Affinity SDK includes a plugin for [Claude Code](https://claude.ai/code) that helps Claude understand how to use the SDK and CLI correctly.

## What it provides

- **Automatic knowledge** - When you ask Claude to write scripts that use the Affinity SDK or CLI, it automatically knows the correct patterns
- **Quick reference command** - Use `/affinity-help` for a quick reference

## Installation

```bash
# Add the marketplace (one-time)
/plugin marketplace add yaniv-golan/affinity-sdk

# Install the plugin
/plugin install affinity-sdk@affinity-sdk
```

## Usage

Once installed, Claude automatically applies the correct patterns when you ask it to:

- Write scripts to export Affinity data
- Query companies, persons, or opportunities
- Work with list entries and custom fields
- Use the `xaffinity` CLI

### Example prompts

- "Write a script to export all companies to CSV"
- "How do I filter persons by a custom field?"
- "Get all entries from my Deal Pipeline list"

### Quick reference

Run `/affinity-help` to see a quick reference of SDK and CLI patterns.

## What Claude learns

The plugin teaches Claude these critical patterns:

### Use typed IDs (not raw integers)

```python
from affinity.types import PersonId, CompanyId

client.persons.get(PersonId(123))     # ✅ Correct
client.persons.get(123)               # ❌ Wrong
```

### Use context managers

```python
with Affinity.from_env() as client:   # ✅ Correct
    ...

client = Affinity.from_env()          # ❌ May leak resources
```

### Filters only work on custom fields

```python
from affinity import F

# ✅ Works - custom fields
client.persons.list(filter=F.field("Department").equals("Sales"))

# ❌ Won't work - built-in properties
# firstName, lastName, type, domain, name, etc.
```

## Updating the plugin

To get the latest version:

```bash
/plugin marketplace update
/plugin update affinity-sdk@affinity-sdk
```

## Uninstalling

```bash
/plugin uninstall affinity-sdk@affinity-sdk
```
