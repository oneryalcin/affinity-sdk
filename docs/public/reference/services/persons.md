# Persons

## Interaction Dates

The `get()` method supports fetching interaction date summaries for a person using the
`with_interaction_dates` parameter. When enabled, the returned `Person` object will have
its `interaction_dates` and `interactions` fields populated with:

- **Last meeting date**: When the last calendar event with this person occurred
- **Next meeting date**: When the next scheduled calendar event is
- **Last email date**: When the last email exchange happened
- **Last interaction date**: The most recent interaction of any type

```python
from affinity import Affinity
from affinity.types import PersonId

with Affinity(api_key="YOUR_API_KEY") as client:
    # Fetch person with interaction dates
    person = client.persons.get(
        PersonId(456),
        with_interaction_dates=True,
        with_interaction_persons=True,  # Include person IDs for each interaction
    )

    # Access interaction data
    if person.interaction_dates:
        print(f"Last meeting: {person.interaction_dates.last_event_date}")
        print(f"Next meeting: {person.interaction_dates.next_event_date}")
        print(f"Last email: {person.interaction_dates.last_email_date}")

    # Access team member IDs from interactions
    if person.interactions and person.interactions.last_event:
        team_ids = person.interactions.last_event.person_ids
        print(f"Last meeting attendees: {team_ids}")
```

::: affinity.services.persons.PersonService

::: affinity.services.persons.AsyncPersonService
