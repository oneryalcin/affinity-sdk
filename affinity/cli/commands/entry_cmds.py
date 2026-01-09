"""Top-level 'entry' command group - shorthand for 'list entry'."""

from __future__ import annotations

from ..click_compat import RichGroup, click

# Import the underlying command functions from list_cmds
# These are Click Command objects after decoration
from .list_cmds import (
    list_entry_add,
    list_entry_delete,
    list_entry_field,
    list_entry_get,
)


@click.group(name="entry", cls=RichGroup)
def entry_group() -> None:
    """List entry commands (shorthand for 'list entry').

    These commands work on list entries, which are the rows within an Affinity list.
    Each entry represents a person, company, or opportunity tracked in that list.

    This is a convenience alias - all commands are also available under 'list entry'.
    """


# Register the same command functions under the entry group
# Click commands can be added to multiple groups
entry_group.add_command(list_entry_get, name="get")
entry_group.add_command(list_entry_add, name="add")
entry_group.add_command(list_entry_delete, name="delete")
entry_group.add_command(list_entry_field, name="field")
