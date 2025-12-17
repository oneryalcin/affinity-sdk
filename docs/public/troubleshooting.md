# Troubleshooting

## 401 / 403 errors

- Verify your API key is correct.
- Ensure the key has access to the entities you’re querying.

## Rate limits

The client tracks rate-limit state and retries some requests automatically.
See [Client](reference/client.md) and [Exceptions](reference/exceptions.md).

## Debugging

Enable hooks (`guides/debugging-hooks.md`) or set `log_requests=True` on the client.

## Next steps

- [Getting started](getting-started.md)
- [Examples](examples.md)
- [Debugging hooks](guides/debugging-hooks.md)
- [Errors & retries](guides/errors-and-retries.md)
