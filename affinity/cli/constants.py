"""CLI-specific constants.

Exit codes follow standard conventions:
- 0: Success
- 1-99: Error codes
- 100+: Special status codes (success with side-effects)
- 126-127: Shell reserved
- 128+: Signal-based exits (shell convention)
"""

# Standard exit codes
EXIT_SUCCESS = 0
EXIT_ERROR = 1

# Special status codes (success, but with additional information)
EXIT_TRUNCATED = 100  # Output was truncated due to size limits
