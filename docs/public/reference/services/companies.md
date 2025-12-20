# Companies

Note: `CompanyService` includes two **v1-only** exceptions for company -> people associations:
`get_associated_person_ids(...)` and `get_associated_people(...)`. V2 does not expose a direct
company -> people relationship endpoint, so these methods use the v1 organizations API under
the hood. They are documented as exceptions and may be superseded when v2 adds parity.

::: affinity.services.companies.CompanyService

::: affinity.services.companies.AsyncCompanyService
