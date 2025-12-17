# Examples

All examples assume `AFFINITY_API_KEY` is set:

```bash
export AFFINITY_API_KEY="your-api-key"
```

Run an example with:

```bash
python examples/basic_usage.py
```

## Basic

- [`examples/basic_usage.py`](https://github.com/yaniv-golan/affinity-sdk/blob/main/examples/basic_usage.py) — small end-to-end tour of core services
- [`examples/advanced_usage.py`](https://github.com/yaniv-golan/affinity-sdk/blob/main/examples/advanced_usage.py) — deeper patterns and best practices

## Async

- [`examples/async_lifecycle.py`](https://github.com/yaniv-golan/affinity-sdk/blob/main/examples/async_lifecycle.py) — async client lifecycle and usage

## Filtering and hooks

- [`examples/filter_builder.py`](https://github.com/yaniv-golan/affinity-sdk/blob/main/examples/filter_builder.py) — build V2 filter expressions with `affinity.F`
- [`examples/hooks_debugging.py`](https://github.com/yaniv-golan/affinity-sdk/blob/main/examples/hooks_debugging.py) — request/response hooks for debugging

## Lists, resolve helpers, tasks

- [`examples/list_management.py`](https://github.com/yaniv-golan/affinity-sdk/blob/main/examples/list_management.py) — list CRUD and entry operations
- [`examples/resolve_helpers.py`](https://github.com/yaniv-golan/affinity-sdk/blob/main/examples/resolve_helpers.py) — resolve helpers (IDs from external identifiers)
- [`examples/task_polling.py`](https://github.com/yaniv-golan/affinity-sdk/blob/main/examples/task_polling.py) — polling long-running tasks
