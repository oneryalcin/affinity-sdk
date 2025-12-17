# API versions & SDK routing

??? info "Quick glossary"
    - **V1 API**: legacy endpoints at `https://api.affinity.co`
    - **V2 API**: newer endpoints at `https://api.affinity.co/v2`
    - **V2 API version**: dated versions like `2024-01-01` within V2 (configured in Affinity)
    - **Default API Version**: your Affinity setting that selects the V2 version
    - **Beta endpoints**: newer V2 endpoints that require opt-in

The SDK prefers V2 endpoints where available and falls back to V1 for operations not yet supported in V2.

## What this means in practice

- **Reads** (list/get/search) are typically **V2**.
- **Writes** (create/update/delete) are often **V1** today.

Example: companies

- `client.companies.get(...)` uses V2
- `client.companies.create(...)` uses V1

## Beta endpoints

Some V2 endpoints are gated behind `enable_beta_endpoints=True`. If you call a beta endpoint without opt-in, the SDK raises `BetaEndpointDisabledError`.

## Version compatibility errors

If Affinity changes V2 response shapes (or your API key is pinned to an unexpected V2 version), parsing can fail with `VersionCompatibilityError`.

Suggested steps:

1. Check your API key’s “Default API Version” in the Affinity dashboard.
2. Set `expected_v2_version=...` if you want that mismatch called out in errors.

References:

- V1 docs: https://api-docs.affinity.co/
- V2 portal: https://developer.affinity.co/
- V2 versioning: https://developer.affinity.co/#section/Getting-Started/Versioning
- Glossary: ../glossary.md

## Next steps

- [Configuration](configuration.md)
- [Sync vs async](sync-vs-async.md)
- [Errors & retries](errors-and-retries.md)
