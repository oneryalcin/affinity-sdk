## CLI Command PR Checklist

**Type of Change**:
- [ ] New CLI command
- [ ] CLI command modification
- [ ] CLI infrastructure change

### Code Quality

- [ ] Uses `serialize_model_for_cli()` for all model serialization
- [ ] No direct `model_dump()` calls (or documented exception with TODO comment)
- [ ] Pagination key matches data key (if applicable)
- [ ] Resolved metadata follows standard structure (if applicable)
- [ ] Similar commands updated if pattern changed

### Testing

- [ ] Integration test includes `--json` flag
- [ ] JSON output verified to parse correctly
- [ ] All tests passing (505+ tests)
- [ ] Cross-command consistency tested (if CRUD operation)

### Documentation

- [ ] Help text (`--help`) updated with clear examples
- [ ] Docstring includes:
  - [ ] Description of what the command does
  - [ ] Explanation of selector formats (if applicable)
  - [ ] JSON output behavior documentation (if applicable)
  - [ ] At least 3 usage examples
- [ ] Special JSON behavior documented (if any)
- [ ] CLI reference documentation updated (if user-facing change)

### Pre-Commit Hooks

- [ ] All pre-commit hooks passing (ruff, mypy, check-cli-patterns)
- [ ] If bypassing `check-cli-patterns`, justification documented with TODO comment

### Related Issues

Closes #

### Description

<!-- Provide a brief description of what this PR does -->

### Command Examples

<!-- If applicable, add command output examples showing both table and JSON output -->

**Table output:**
```bash
$ affinity my-command 12345
# Output here
```

**JSON output:**
```bash
$ affinity my-command 12345 --json
{
  "ok": true,
  "command": "my-command",
  "data": {
    ...
  }
}
```

### Breaking Changes

<!-- List any breaking changes, or write "None" -->

### Reviewer Notes

<!-- Any special considerations for reviewers? -->

---

## For Reviewers

When reviewing CLI command PRs, verify:

1. **Serialization Pattern**: All models use `serialize_model_for_cli()` or have documented exceptions
2. **JSON Safety**: Test with `--json` flag to ensure output parses correctly
3. **Documentation**: Help text is clear and includes good examples
4. **Consistency**: Similar commands follow the same patterns
5. **Testing**: Adequate test coverage, especially for JSON output

See [CLI Development Guide](../../docs/cli-development-guide.md) for detailed patterns and best practices.
