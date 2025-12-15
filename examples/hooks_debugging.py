"""
Request/response hook example for the Affinity SDK (DX-008).

This example demonstrates:
- Using `on_request` / `on_response` hooks for lightweight debugging
- Accessing sanitized request/response metadata (no API key leakage)
"""

import os

from affinity import Affinity
from affinity.hooks import RequestInfo, ResponseInfo


def on_request(req: RequestInfo) -> None:
    print(f">> {req.method} {req.url}")


def on_response(resp: ResponseInfo) -> None:
    print(
        f"<< {resp.status_code} ({resp.elapsed_ms:.0f}ms) {resp.request.method} {resp.request.url}"
    )


def main() -> None:
    api_key = os.environ.get("AFFINITY_API_KEY")
    if not api_key:
        print("Please set AFFINITY_API_KEY environment variable")
        return

    with Affinity(
        api_key=api_key,
        on_request=on_request,
        on_response=on_response,
    ) as client:
        _ = client.auth.whoami()


if __name__ == "__main__":
    main()
