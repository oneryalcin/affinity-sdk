# Companies

Note: `CompanyService` includes two **v1-only** exceptions for company -> people associations:
`get_associated_person_ids(...)` and `get_associated_people(...)`. V2 does not expose a direct
company -> people relationship endpoint, so these methods use the v1 organizations API under
the hood. They are documented as exceptions and may be superseded when v2 adds parity.

## Interaction Dates

The `get()` method supports fetching interaction date summaries for a company using the
`with_interaction_dates` parameter. When enabled, the returned `Company` object will have
its `interaction_dates` and `interactions` fields populated with:

- **Last meeting date**: When the last calendar event with this company occurred
- **Next meeting date**: When the next scheduled calendar event is
- **Last email date**: When the last email exchange happened
- **Last interaction date**: The most recent interaction of any type

```python
from affinity import Affinity
from affinity.types import CompanyId

with Affinity(api_key="YOUR_API_KEY") as client:
    # Fetch company with interaction dates
    company = client.companies.get(
        CompanyId(123),
        with_interaction_dates=True,
        with_interaction_persons=True,  # Include person IDs for each interaction
    )

    # Access interaction data
    if company.interaction_dates:
        print(f"Last meeting: {company.interaction_dates.last_event_date}")
        print(f"Next meeting: {company.interaction_dates.next_event_date}")
        print(f"Last email: {company.interaction_dates.last_email_date}")

    # Access team member IDs from interactions
    if company.interactions and company.interactions.last_event:
        person_ids = company.interactions.last_event.person_ids
        print(f"Last meeting attendees: {person_ids}")
```

::: affinity.services.companies.CompanyService

::: affinity.services.companies.AsyncCompanyService
