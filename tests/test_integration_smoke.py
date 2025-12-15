from __future__ import annotations

import os

import pytest

from affinity import Affinity


def _api_key() -> str | None:
    return os.environ.get("AFFINITY_API_KEY")


@pytest.mark.integration
@pytest.mark.req("TR-014")
def test_live_smoke_whoami_and_basic_reads() -> None:
    """
    Live smoke test against the real Affinity API.

    This test is skipped unless `AFFINITY_API_KEY` is set.
    It only performs read-only calls.
    """
    api_key = _api_key()
    if not api_key:
        pytest.skip("Set AFFINITY_API_KEY to run live smoke tests")

    with Affinity(api_key=api_key) as client:
        me = client.auth.whoami()
        assert me.user.id is not None
        assert me.tenant.id is not None

        companies = client.companies.list(limit=1)
        assert companies.pagination is not None

        persons = client.persons.list(limit=1)
        assert persons.pagination is not None
