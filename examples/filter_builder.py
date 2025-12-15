"""
Filter builder example for the Affinity SDK (FR-007).

This example demonstrates:
- Building V2 filter expressions with `affinity.F`
- Passing a filter expression directly to `.list()` / `.all()`
"""

import os

from affinity import Affinity, F
from affinity.types import FieldType


def main() -> None:
    api_key = os.environ.get("AFFINITY_API_KEY")
    if not api_key:
        print("Please set AFFINITY_API_KEY environment variable")
        return

    # Build a safe, escaped filter expression.
    filter_expr = F.field("domain").contains("acme")
    print(f"Filter: {filter_expr}")

    with Affinity(api_key=api_key) as client:
        companies = client.companies.list(
            filter=filter_expr,
            field_types=[FieldType.ENRICHED],
            limit=5,
        )
        for company in companies.data:
            print(f"- {company.name} ({company.domain})")


if __name__ == "__main__":
    main()
