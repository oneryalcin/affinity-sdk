# Glossary

## API generations (V1 vs V2)

- **V1 API**: legacy Affinity endpoints at `https://api.affinity.co`
- **V2 API**: newer Affinity endpoints at `https://api.affinity.co/v2`

## V2 API version

V2 has dated versions (for example `2024-01-01`). In the Affinity dashboard, your API key has a “Default API Version” setting that selects the V2 version used for your requests.

## Beta endpoints

Some V2 endpoints are opt-in and require `enable_beta_endpoints=True` in this SDK.

## Typed IDs

The SDK uses typed ID classes (e.g. `CompanyId`, `PersonId`, `ListId`) to reduce accidental mixups.

## Field values

Entities expose `fields`, and `fields.requested` indicates whether field data was requested and returned by the API.
