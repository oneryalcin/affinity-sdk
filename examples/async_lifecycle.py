"""
Async lifecycle example for the Affinity SDK (DX-009).

This example demonstrates:
- Preferred: `async with AsyncAffinity(...)` for automatic cleanup
- Alternative: explicit `await client.close()` in a `finally`
"""

import asyncio
import os

from affinity import AsyncAffinity


async def context_manager_example(api_key: str) -> None:
    async with AsyncAffinity(api_key=api_key) as client:
        companies = await client.companies.list(limit=1)
        if companies.data:
            print(f"First company: {companies.data[0].name}")


async def explicit_close_example(api_key: str) -> None:
    client = AsyncAffinity(api_key=api_key)
    try:
        companies = await client.companies.list(limit=1)
        if companies.data:
            print(f"First company: {companies.data[0].name}")
    finally:
        await client.close()


def main() -> None:
    api_key = os.environ.get("AFFINITY_API_KEY")
    if not api_key:
        print("Please set AFFINITY_API_KEY environment variable")
        return

    asyncio.run(context_manager_example(api_key))
    asyncio.run(explicit_close_example(api_key))


if __name__ == "__main__":
    main()
