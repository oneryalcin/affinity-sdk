"""
Basic usage example for the Affinity SDK.

This example demonstrates:
- Initializing the client
- Listing companies and persons
- Using pagination
- Accessing field data
"""

import os

from affinity import Affinity
from affinity.types import FieldType, PersonType


def main() -> None:
    # Get API key from environment
    api_key = os.environ.get("AFFINITY_API_KEY")
    if not api_key:
        print("Please set AFFINITY_API_KEY environment variable")
        return

    # Initialize the client with context manager for automatic cleanup
    with Affinity(api_key=api_key) as client:
        # Get current user info
        me = client.auth.whoami()
        print(f"Logged in as: {me.user.first_name} {me.user.last_name}")
        print(f"Tenant: {me.tenant.name}")
        print()

        # List companies with enriched data
        print("Companies (first page):")
        print("-" * 50)
        companies = client.companies.list(
            field_types=[FieldType.ENRICHED],
            limit=5,
        )
        for company in companies.data:
            print(f"  {company.name}")
            if company.domain:
                print(f"    Domain: {company.domain}")
            if company.fields:
                print(f"    Fields: {len(company.fields)} values")
        print()

        # Iterate through all internal team members
        print("Internal team members:")
        print("-" * 50)
        for person in client.persons.all():
            if person.type == PersonType.INTERNAL:
                email = person.primary_email or "(no email)"
                print(f"  {person.first_name} {person.last_name} <{email}>")
        print()

        # List all lists
        print("Lists:")
        print("-" * 50)
        for lst in client.lists.all():
            print(f"  [{lst.type.name}] {lst.name}")
        print()

        # Show rate limit status
        print("Rate limits:")
        print("-" * 50)
        state = client.rate_limit_state
        print(f"  User remaining: {state['user_remaining']}")
        print(f"  Org remaining: {state['org_remaining']}")


if __name__ == "__main__":
    main()
