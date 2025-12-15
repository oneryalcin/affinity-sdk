"""
Resolve helper examples for the Affinity SDK (FR-010).

This example demonstrates:
- `companies.resolve(domain=...)` convenience lookup via V1 search
- `persons.resolve(email=...)` convenience lookup via V1 search
"""

import os

from affinity import Affinity


def main() -> None:
    api_key = os.environ.get("AFFINITY_API_KEY")
    if not api_key:
        print("Please set AFFINITY_API_KEY environment variable")
        return

    company_domain = os.environ.get("AFFINITY_RESOLVE_COMPANY_DOMAIN", "acme.com")
    person_email = os.environ.get("AFFINITY_RESOLVE_PERSON_EMAIL", "jane@example.com")

    with Affinity(api_key=api_key) as client:
        company = client.companies.resolve(domain=company_domain)
        if company:
            print(f"Company: {company.name} ({company.domain})")
        else:
            print(f"No company found for domain={company_domain!r}")

        person = client.persons.resolve(email=person_email)
        if person:
            print(f"Person: {person.first_name} {person.last_name} <{person.primary_email}>")
        else:
            print(f"No person found for email={person_email!r}")


if __name__ == "__main__":
    main()
