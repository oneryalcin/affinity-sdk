# Working with Opportunity Associations

Opportunities in Affinity can be linked to People and Companies. Due to API limitations, these associations require special handling.

## The V2 Limitation

When you retrieve opportunities via standard methods, person and company associations may be empty:

```python
opp = client.opportunities.get(OpportunityId(123))
print(opp.person_ids)  # [] - empty!
```

This is because the V2 API returns a "partial representation" that omits association data.

??? info "Why does this happen?"
    The Affinity V2 API returns opportunities without `personIds` or `companyIds` fields. This is a known limitation. The V1 API includes these associations, so the SDK provides explicit methods to fetch them.

## Getting Associations

Use the dedicated association methods:

```python
from affinity.types import OpportunityId

# Get person IDs only (1 API call)
person_ids = client.opportunities.get_associated_person_ids(OpportunityId(123))

# Get full Person objects (1 + N API calls)
people = client.opportunities.get_associated_people(OpportunityId(123))

# Same for companies
company_ids = client.opportunities.get_associated_company_ids(OpportunityId(123))
companies = client.opportunities.get_associated_companies(OpportunityId(123))
```

### Getting Both at Once

If you need both person and company associations, use `get_associations()` to save an API call:

```python
# Single V1 call returns both
assoc = client.opportunities.get_associations(OpportunityId(123))
print(assoc.person_ids)   # [PersonId(1001), PersonId(1002)]
print(assoc.company_ids)  # [CompanyId(2001)]
```

The return type is a `NamedTuple` with IDE autocomplete support.

## Batch Operations

When working with lists of opportunities, use the batch helper:

```python
from affinity.types import ListId, OpportunityId

# Step 1: Get all opportunity IDs from a list
opp_ids = [
    OpportunityId(entry.entity.id)
    for entry in client.lists.entries(ListId(123)).all()
]

# Step 2: Fetch associations for all (1 API call per opportunity)
associations = client.opportunities.get_associated_person_ids_batch(opp_ids)

# Step 3: Collect all unique person IDs
all_person_ids = set()
for person_ids in associations.values():
    all_person_ids.update(person_ids)
```

### Error Handling in Batch Operations

By default, the batch helper raises on the first error. Use `on_error="skip"` to continue:

```python
# Skip failed IDs instead of raising
associations = client.opportunities.get_associated_person_ids_batch(
    opp_ids,
    on_error="skip",  # Default is "raise"
)
# Only successfully fetched opportunities are in the result
```

## Limiting Results

All association methods support `max_results` to limit the number of items returned:

```python
# Get at most 5 associated people
people = client.opportunities.get_associated_people(
    OpportunityId(123),
    max_results=5,
)
```

## API Cost

| Method | API Calls |
|--------|-----------|
| `get_associated_person_ids()` | 1 |
| `get_associated_company_ids()` | 1 |
| `get_associations()` | 1 |
| `get_associated_people()` | 1 + N (N = people count) |
| `get_associated_companies()` | 1 + N (N = company count) |
| `get_associated_person_ids_batch()` | N (N = opportunity count) |

!!! warning "Rate Limits"
    For large associations (N > 50), be aware of rate limit implications. Consider using `max_results` to limit the number of full object fetches.

## Async Support

All methods have async equivalents in `AsyncOpportunityService`:

```python
# Async version
person_ids = await client.opportunities.get_associated_person_ids(OpportunityId(123))
```

## Alternative: `get_details()`

If you need the full opportunity object including associations, use `get_details()`:

```python
opp = client.opportunities.get_details(OpportunityId(123))
print(opp.person_ids)  # Now populated!
```

This is useful when you need other opportunity fields alongside associations.

## Next Steps

- [Pagination](pagination.md) - for iterating large result sets
- [Rate Limits](rate-limits.md) - understanding API quotas
- [API Versions](api-versions-and-routing.md) - V1 vs V2 behavior
