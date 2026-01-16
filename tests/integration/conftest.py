"""
Pytest configuration for integration tests.

Integration tests run against a live Affinity sandbox environment.
They are skipped by default (see pyproject.toml addopts).

To run integration tests:
    pytest -m integration
    pytest tests/integration/

API key is loaded from .sandbox.env file in project root.
"""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest

from affinity import Affinity
from affinity.types import UserId


def load_sandbox_api_key() -> str | None:
    """
    Load API key from .sandbox.env file.

    The .sandbox.env file should be in the project root and contain:
        AFFINITY_API_KEY=your_sandbox_api_key_here

    Returns the API key if found, None otherwise.
    """
    # Try to find .sandbox.env relative to this file or in common locations
    possible_paths = [
        Path(__file__).parent.parent.parent / ".sandbox.env",  # project root
        Path.cwd() / ".sandbox.env",  # current working directory
    ]

    for env_file in possible_paths:
        if env_file.exists():
            with env_file.open() as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("AFFINITY_API_KEY="):
                        return line.split("=", 1)[1].strip()
    return None


@pytest.fixture(scope="session")
def sandbox_api_key() -> str:
    """
    Get API key from .sandbox.env, skip if not available.

    This fixture ensures integration tests only run when a sandbox
    API key is properly configured.
    """
    api_key = load_sandbox_api_key()
    if not api_key:
        pytest.skip(
            "Integration tests require .sandbox.env file with AFFINITY_API_KEY. "
            "See tests/integration/README.md for setup instructions."
        )
    return api_key


@pytest.fixture(scope="session")
def sandbox_client(sandbox_api_key: str) -> Generator[Affinity, None, None]:
    """
    Create an Affinity client connected to a sandbox environment.

    This fixture:
    1. Creates a client with the sandbox API key
    2. Verifies the instance is a sandbox (tenant name ends with 'sandbox')
    3. Yields the client for tests
    4. Closes the client after all tests complete

    Tests using this fixture will be skipped if:
    - No .sandbox.env file exists
    - The API key is not for a sandbox instance
    """
    client = Affinity(api_key=sandbox_api_key)

    try:
        # Verify this is a sandbox instance
        whoami = client.auth.whoami()
        tenant_name = whoami.tenant.name.lower()

        if not tenant_name.endswith("sandbox"):
            pytest.fail(
                f"Integration tests require a SANDBOX instance. "
                f"Tenant '{whoami.tenant.name}' does not end with 'sandbox'. "
                f"This is a safety check to prevent accidental writes to production data."
            )

        yield client
    finally:
        client.close()


@pytest.fixture(scope="session")
def sandbox_user_id(sandbox_client: Affinity) -> UserId:
    """Get the authenticated user's ID from the sandbox client."""
    whoami = sandbox_client.auth.whoami()
    return whoami.user.id


@pytest.fixture(scope="session")
def sandbox_info(sandbox_client: Affinity) -> dict:
    """
    Get sandbox instance info for test diagnostics.

    Returns dict with tenant name, subdomain, user name, etc.
    """
    whoami = sandbox_client.auth.whoami()
    return {
        "tenant_name": whoami.tenant.name,
        "subdomain": whoami.tenant.subdomain,
        "user_name": f"{whoami.user.first_name} {whoami.user.last_name}",
        "user_id": whoami.user.id,
        "scopes": whoami.grant.scopes,
    }
