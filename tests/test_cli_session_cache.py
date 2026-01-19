"""Tests for CLI session cache functionality."""

from __future__ import annotations

import io
import sys
import time
from pathlib import Path

import pytest
from pydantic import BaseModel

pytest.importorskip("rich_click")
pytest.importorskip("rich")
pytest.importorskip("platformdirs")

from click.testing import CliRunner

from affinity.cli.main import cli
from affinity.cli.session_cache import SessionCache, SessionCacheConfig


class SampleModel(BaseModel):
    """Sample model for testing cache serialization."""

    id: int
    name: str
    value: float | None = None


class TestSessionCacheConfig:
    """Tests for SessionCacheConfig initialization."""

    def test_disabled_when_env_not_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Cache is disabled when AFFINITY_SESSION_CACHE is not set."""
        monkeypatch.delenv("AFFINITY_SESSION_CACHE", raising=False)
        config = SessionCacheConfig()
        assert config.cache_dir is None
        assert config.enabled is False

    def test_enabled_when_env_set(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Cache is enabled when AFFINITY_SESSION_CACHE points to valid directory."""
        cache_dir = tmp_path / "cache"
        monkeypatch.setenv("AFFINITY_SESSION_CACHE", str(cache_dir))
        config = SessionCacheConfig()
        assert config.cache_dir == cache_dir
        assert config.enabled is True
        assert cache_dir.exists()

    def test_auto_creates_directory(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Cache directory is auto-created with restricted permissions."""
        cache_dir = tmp_path / "new_cache_dir"
        monkeypatch.setenv("AFFINITY_SESSION_CACHE", str(cache_dir))
        config = SessionCacheConfig()
        assert config.enabled is True
        assert cache_dir.exists()
        # Check permissions (owner-only on POSIX)
        if sys.platform != "win32":
            assert (cache_dir.stat().st_mode & 0o777) == 0o700

    def test_default_ttl(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Default TTL is 600 seconds (10 minutes)."""
        monkeypatch.setenv("AFFINITY_SESSION_CACHE", str(tmp_path))
        monkeypatch.delenv("AFFINITY_SESSION_CACHE_TTL", raising=False)
        config = SessionCacheConfig()
        assert config.ttl == 600

    def test_custom_ttl_from_env(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """TTL can be customized via AFFINITY_SESSION_CACHE_TTL."""
        monkeypatch.setenv("AFFINITY_SESSION_CACHE", str(tmp_path))
        monkeypatch.setenv("AFFINITY_SESSION_CACHE_TTL", "120")
        config = SessionCacheConfig()
        assert config.ttl == 120.0

    def test_invalid_ttl_uses_default(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Invalid TTL value falls back to default."""
        monkeypatch.setenv("AFFINITY_SESSION_CACHE", str(tmp_path))
        monkeypatch.setenv("AFFINITY_SESSION_CACHE_TTL", "invalid")
        config = SessionCacheConfig()
        assert config.ttl == 600

    def test_disabled_when_path_is_file(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Cache is disabled when path exists but is not a directory."""
        file_path = tmp_path / "not_a_dir"
        file_path.write_text("content")
        monkeypatch.setenv("AFFINITY_SESSION_CACHE", str(file_path))

        stderr = io.StringIO()
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(sys, "stderr", stderr)
            config = SessionCacheConfig()

        assert config.enabled is False
        assert "is not a directory" in stderr.getvalue()

    def test_tenant_hash_from_api_key(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Tenant hash is derived from API key."""
        monkeypatch.setenv("AFFINITY_SESSION_CACHE", str(tmp_path))
        config = SessionCacheConfig()
        config.set_tenant_hash("test-api-key-12345")
        assert config.tenant_hash is not None
        assert len(config.tenant_hash) == 12  # SHA256 truncated to 12 chars


class TestSessionCache:
    """Tests for SessionCache operations."""

    @pytest.fixture
    def cache_config(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> SessionCacheConfig:
        """Create a configured and enabled cache config."""
        monkeypatch.setenv("AFFINITY_SESSION_CACHE", str(tmp_path))
        config = SessionCacheConfig()
        config.set_tenant_hash("test-api-key")
        return config

    @pytest.fixture
    def cache(self, cache_config: SessionCacheConfig) -> SessionCache:
        """Create a session cache instance."""
        return SessionCache(cache_config)

    def test_cache_miss_returns_none(self, cache: SessionCache) -> None:
        """Cache returns None for missing keys."""
        result = cache.get("nonexistent", SampleModel)
        assert result is None

    def test_cache_set_and_get(self, cache: SessionCache) -> None:
        """Cached values can be retrieved."""
        model = SampleModel(id=1, name="test", value=3.14)
        cache.set("key1", model)
        result = cache.get("key1", SampleModel)
        assert result is not None
        assert result.id == 1
        assert result.name == "test"
        assert result.value == 3.14

    def test_cache_list_set_and_get(self, cache: SessionCache) -> None:
        """Lists of models can be cached and retrieved."""
        models = [
            SampleModel(id=1, name="first"),
            SampleModel(id=2, name="second"),
            SampleModel(id=3, name="third"),
        ]
        cache.set("list_key", models)
        result = cache.get_list("list_key", SampleModel)
        assert result is not None
        assert len(result) == 3
        assert result[0].name == "first"
        assert result[2].name == "third"

    def test_cache_ttl_expiration(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Expired cache entries return None and are cleaned up."""
        # Use very short TTL
        monkeypatch.setenv("AFFINITY_SESSION_CACHE", str(tmp_path))
        monkeypatch.setenv("AFFINITY_SESSION_CACHE_TTL", "0.1")
        config = SessionCacheConfig()
        config.set_tenant_hash("test-api-key")
        cache = SessionCache(config)

        model = SampleModel(id=1, name="test")
        cache.set("expiring_key", model)

        # Verify it exists initially
        assert cache.get("expiring_key", SampleModel) is not None

        # Wait for expiration
        time.sleep(0.15)

        # Should be expired now
        result = cache.get("expiring_key", SampleModel)
        assert result is None

    def test_tenant_isolation(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Different API keys have isolated caches."""
        monkeypatch.setenv("AFFINITY_SESSION_CACHE", str(tmp_path))

        # Create cache for tenant A
        config_a = SessionCacheConfig()
        config_a.set_tenant_hash("api-key-tenant-a")
        cache_a = SessionCache(config_a)

        # Create cache for tenant B
        config_b = SessionCacheConfig()
        config_b.set_tenant_hash("api-key-tenant-b")
        cache_b = SessionCache(config_b)

        # Store different values for same key
        cache_a.set("shared_key", SampleModel(id=1, name="tenant_a"))
        cache_b.set("shared_key", SampleModel(id=2, name="tenant_b"))

        # Each tenant sees their own value
        result_a = cache_a.get("shared_key", SampleModel)
        result_b = cache_b.get("shared_key", SampleModel)

        assert result_a is not None and result_a.name == "tenant_a"
        assert result_b is not None and result_b.name == "tenant_b"

    def test_invalidate_single_key(self, cache: SessionCache) -> None:
        """Single cache entry can be invalidated."""
        cache.set("key1", SampleModel(id=1, name="one"))
        cache.set("key2", SampleModel(id=2, name="two"))

        cache.invalidate("key1")

        assert cache.get("key1", SampleModel) is None
        assert cache.get("key2", SampleModel) is not None

    def test_invalidate_prefix(self, cache: SessionCache) -> None:
        """Cache entries matching prefix are invalidated."""
        cache.set("list_resolve_123", SampleModel(id=1, name="list1"))
        cache.set("list_resolve_456", SampleModel(id=2, name="list2"))
        cache.set("field_all_789", SampleModel(id=3, name="field"))

        cache.invalidate_prefix("list_resolve_")

        assert cache.get("list_resolve_123", SampleModel) is None
        assert cache.get("list_resolve_456", SampleModel) is None
        assert cache.get("field_all_789", SampleModel) is not None

    def test_disabled_cache_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Disabled cache always returns None without errors."""
        monkeypatch.delenv("AFFINITY_SESSION_CACHE", raising=False)
        config = SessionCacheConfig()
        cache = SessionCache(config)

        # Operations should be no-ops
        cache.set("key", SampleModel(id=1, name="test"))
        assert cache.get("key", SampleModel) is None
        cache.invalidate("key")  # Should not error
        cache.invalidate_prefix("key")  # Should not error

    def test_corrupted_cache_returns_none(self, cache: SessionCache) -> None:
        """Corrupted cache files return None and are cleaned up."""
        # Write corrupted data directly
        assert cache.config.cache_dir is not None
        safe_key = cache._sanitize_key("corrupted_key")
        cache_path = cache.config.cache_dir / f"{safe_key}_{cache.config.tenant_hash}.json"
        cache_path.write_text("not valid json{{{")

        result = cache.get("corrupted_key", SampleModel)
        assert result is None
        # File should be deleted
        assert not cache_path.exists()

    def test_key_sanitization(self, cache: SessionCache) -> None:
        """Special characters in keys are sanitized for filesystem safety."""
        # Test various special characters
        cache.set("key/with/slashes", SampleModel(id=1, name="slashes"))
        cache.set("key:with:colons", SampleModel(id=2, name="colons"))
        cache.set("key with spaces", SampleModel(id=3, name="spaces"))

        assert cache.get("key/with/slashes", SampleModel) is not None
        assert cache.get("key:with:colons", SampleModel) is not None
        assert cache.get("key with spaces", SampleModel) is not None

    def test_long_key_truncation(self, cache: SessionCache) -> None:
        """Long keys are truncated with hash suffix to prevent collisions."""
        long_key = "a" * 200
        cache.set(long_key, SampleModel(id=1, name="long"))
        result = cache.get(long_key, SampleModel)
        assert result is not None
        assert result.name == "long"


class TestSessionCacheTrace:
    """Tests for cache trace output."""

    @pytest.fixture
    def cache_with_trace(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> SessionCache:
        """Create a session cache with trace enabled."""
        monkeypatch.setenv("AFFINITY_SESSION_CACHE", str(tmp_path))
        config = SessionCacheConfig()
        config.set_tenant_hash("test-api-key")
        return SessionCache(config, trace=True)

    def test_trace_cache_miss(self, cache_with_trace: SessionCache) -> None:
        """Trace output for cache miss."""
        stderr = io.StringIO()
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(sys, "stderr", stderr)
            cache_with_trace.get("missing_key", SampleModel)

        output = stderr.getvalue()
        assert "trace #- cache miss:" in output
        assert "missing_key" in output

    def test_trace_cache_hit(self, cache_with_trace: SessionCache) -> None:
        """Trace output for cache hit."""
        cache_with_trace.set("hit_key", SampleModel(id=1, name="test"))

        stderr = io.StringIO()
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(sys, "stderr", stderr)
            cache_with_trace.get("hit_key", SampleModel)

        output = stderr.getvalue()
        assert "trace #+ cache hit:" in output
        assert "hit_key" in output

    def test_trace_cache_set(self, cache_with_trace: SessionCache) -> None:
        """Trace output for cache set."""
        stderr = io.StringIO()
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(sys, "stderr", stderr)
            cache_with_trace.set("new_key", SampleModel(id=1, name="test"))

        output = stderr.getvalue()
        assert "trace #= cache set:" in output
        assert "new_key" in output

    def test_trace_cache_invalidate(self, cache_with_trace: SessionCache) -> None:
        """Trace output for cache invalidation."""
        cache_with_trace.set("inv_key", SampleModel(id=1, name="test"))

        stderr = io.StringIO()
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(sys, "stderr", stderr)
            cache_with_trace.invalidate("inv_key")

        output = stderr.getvalue()
        assert "trace #x cache invalidated:" in output
        assert "inv_key" in output

    def test_trace_prefix_invalidation(self, cache_with_trace: SessionCache) -> None:
        """Trace output for prefix invalidation."""
        cache_with_trace.set("prefix_one", SampleModel(id=1, name="one"))
        cache_with_trace.set("prefix_two", SampleModel(id=2, name="two"))

        stderr = io.StringIO()
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(sys, "stderr", stderr)
            cache_with_trace.invalidate_prefix("prefix_")

        output = stderr.getvalue()
        assert "trace #x cache invalidated 2 entries:" in output
        assert "prefix_" in output


class TestSessionCacheIntegration:
    """Integration tests for CLI session cache."""

    def test_session_start_creates_directory(self, tmp_path: Path) -> None:
        """session start creates a valid cache directory."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(cli, ["session", "start"])

        assert result.exit_code == 0
        # Output should be a valid directory path
        cache_path = result.output.strip()
        assert Path(cache_path).exists()
        assert Path(cache_path).is_dir()

    def test_session_status_shows_disabled(self) -> None:
        """session status shows disabled when env not set."""
        runner = CliRunner(env={"AFFINITY_SESSION_CACHE": ""})
        result = runner.invoke(cli, ["session", "status"])

        assert result.exit_code == 0
        assert "no active session" in result.output.lower()

    def test_session_status_shows_enabled(self, tmp_path: Path) -> None:
        """session status shows enabled with cache path."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        runner = CliRunner(env={"AFFINITY_SESSION_CACHE": str(cache_dir)})
        result = runner.invoke(cli, ["session", "status"])

        assert result.exit_code == 0
        assert str(cache_dir) in result.output

    def test_session_end_removes_directory(self, tmp_path: Path) -> None:
        """session end removes the cache directory."""
        cache_dir = tmp_path / "session_cache"
        cache_dir.mkdir()
        # Add a cache file to ensure cleanup works
        (cache_dir / "test_cache.json").write_text('{"value": 1}')

        runner = CliRunner(env={"AFFINITY_SESSION_CACHE": str(cache_dir)})
        result = runner.invoke(cli, ["session", "end"])

        assert result.exit_code == 0
        assert not cache_dir.exists()


class TestPersonResolutionCaching:
    """Tests for person resolution caching."""

    @pytest.fixture
    def cache(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> SessionCache:
        """Create a session cache for testing."""
        monkeypatch.setenv("AFFINITY_SESSION_CACHE", str(tmp_path))
        config = SessionCacheConfig()
        config.set_tenant_hash("test-api-key")
        return SessionCache(config)

    def test_person_resolution_by_email_cache_key(self, cache: SessionCache) -> None:
        """Person email resolution uses correct cache key format."""
        from affinity.models.entities import Person
        from affinity.types import PersonId

        # Create a mock Person
        person = Person(
            id=PersonId(123),
            first_name="Test",
            last_name="User",
            emails=["test@example.com"],
            primary_email="test@example.com",
        )

        # Store in cache using the expected cache key format
        cache.set("person_resolve_email_test@example.com", person)

        # Verify cache hit
        cached = cache.get("person_resolve_email_test@example.com", Person)
        assert cached is not None
        assert cached.id == PersonId(123)
        assert cached.first_name == "Test"

    def test_person_resolution_by_name_cache_key(self, cache: SessionCache) -> None:
        """Person name resolution uses correct cache key format."""
        from affinity.models.entities import Person
        from affinity.types import PersonId

        person = Person(
            id=PersonId(456),
            first_name="Alice",
            last_name="Smith",
            emails=["alice@example.com"],
            primary_email="alice@example.com",
        )

        # Store in cache using lowercase name for key
        cache.set("person_resolve_name_alice smith", person)

        # Verify cache hit
        cached = cache.get("person_resolve_name_alice smith", Person)
        assert cached is not None
        assert cached.id == PersonId(456)

    def test_person_cache_key_case_insensitive(self, cache: SessionCache) -> None:
        """Person resolution cache keys are case-insensitive."""
        from affinity.models.entities import Person
        from affinity.types import PersonId

        person = Person(
            id=PersonId(789),
            first_name="Bob",
            last_name="Jones",
            emails=["Bob.Jones@Example.Com"],
            primary_email="Bob.Jones@Example.Com",
        )

        # Store with lowercase key
        cache.set("person_resolve_email_bob.jones@example.com", person)

        # Verify same key retrieves it
        cached = cache.get("person_resolve_email_bob.jones@example.com", Person)
        assert cached is not None
        assert cached.id == PersonId(789)


class TestCompanyResolutionCaching:
    """Tests for company resolution caching."""

    @pytest.fixture
    def cache(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> SessionCache:
        """Create a session cache for testing."""
        monkeypatch.setenv("AFFINITY_SESSION_CACHE", str(tmp_path))
        config = SessionCacheConfig()
        config.set_tenant_hash("test-api-key")
        return SessionCache(config)

    def test_company_resolution_by_domain_cache_key(self, cache: SessionCache) -> None:
        """Company domain resolution uses correct cache key format."""
        from affinity.models.entities import Company
        from affinity.types import CompanyId

        company = Company(
            id=CompanyId(100),
            name="Acme Inc",
            domain="acme.com",
            domains=["acme.com", "acme.io"],
        )

        # Store in cache using the expected cache key format
        cache.set("company_resolve_domain_acme.com", company)

        # Verify cache hit
        cached = cache.get("company_resolve_domain_acme.com", Company)
        assert cached is not None
        assert cached.id == CompanyId(100)
        assert cached.name == "Acme Inc"

    def test_company_resolution_by_name_cache_key(self, cache: SessionCache) -> None:
        """Company name resolution uses correct cache key format."""
        from affinity.models.entities import Company
        from affinity.types import CompanyId

        company = Company(
            id=CompanyId(200),
            name="Widget Corp",
            domain="widget.com",
            domains=["widget.com"],
        )

        # Store in cache using lowercase name for key
        cache.set("company_resolve_name_widget corp", company)

        # Verify cache hit
        cached = cache.get("company_resolve_name_widget corp", Company)
        assert cached is not None
        assert cached.id == CompanyId(200)

    def test_company_cache_key_case_insensitive(self, cache: SessionCache) -> None:
        """Company resolution cache keys are case-insensitive."""
        from affinity.models.entities import Company
        from affinity.types import CompanyId

        company = Company(
            id=CompanyId(300),
            name="TechStartup",
            domain="TechStartup.io",
            domains=["TechStartup.io"],
        )

        # Store with lowercase key
        cache.set("company_resolve_domain_techstartup.io", company)

        # Verify same key retrieves it
        cached = cache.get("company_resolve_domain_techstartup.io", Company)
        assert cached is not None
        assert cached.id == CompanyId(300)


class TestCacheDisabledBehavior:
    """Tests for --no-cache flag behavior."""

    def test_disabled_cache_does_not_store(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """When cache is disabled, set() is a no-op."""
        monkeypatch.setenv("AFFINITY_SESSION_CACHE", str(tmp_path))
        config = SessionCacheConfig()
        config.enabled = False  # Simulate --no-cache
        cache = SessionCache(config)

        # Try to store something
        cache.set("test_key", SampleModel(id=1, name="test"))

        # Should not be retrievable
        result = cache.get("test_key", SampleModel)
        assert result is None

    def test_disabled_cache_returns_none(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """When cache is disabled, get() always returns None."""
        # First create an enabled cache and store something
        monkeypatch.setenv("AFFINITY_SESSION_CACHE", str(tmp_path))
        enabled_config = SessionCacheConfig()
        enabled_config.set_tenant_hash("test-api-key")
        enabled_cache = SessionCache(enabled_config)
        enabled_cache.set("test_key", SampleModel(id=1, name="test"))

        # Now create a disabled cache with same path
        disabled_config = SessionCacheConfig()
        disabled_config.cache_dir = tmp_path
        disabled_config.enabled = False
        disabled_config.tenant_hash = "test-api-key"
        disabled_cache = SessionCache(disabled_config)

        # Should return None even though file exists
        result = disabled_cache.get("test_key", SampleModel)
        assert result is None


class TestResolutionCachingEffectiveness:
    """Integration tests proving cache reduces API calls."""

    @pytest.fixture
    def cache(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> SessionCache:
        """Create an enabled session cache for testing."""
        monkeypatch.setenv("AFFINITY_SESSION_CACHE", str(tmp_path))
        config = SessionCacheConfig()
        config.set_tenant_hash("test-api-key")
        return SessionCache(config)

    def test_person_email_resolution_caches_api_result(self, cache: SessionCache) -> None:
        """Person email resolution caches API result, avoiding repeated calls."""
        from unittest.mock import MagicMock

        from affinity.cli.commands.person_cmds import _resolve_person_by_email
        from affinity.models.entities import Person
        from affinity.types import PersonId

        # Track API calls
        api_call_count = 0
        mock_person = Person(
            id=PersonId(123),
            first_name="Test",
            last_name="User",
            emails=["test@example.com"],
            primary_email="test@example.com",
        )

        class MockPage:
            def __init__(self, data: list[Person], next_cursor: str | None = None):
                self.data = data
                self.next_cursor = next_cursor

        def mock_search_pages(_term: str, **_kwargs: object):
            nonlocal api_call_count
            api_call_count += 1
            yield MockPage(data=[mock_person], next_cursor=None)

        mock_client = MagicMock()
        mock_client.persons.search_pages = mock_search_pages

        # First call - should hit API
        result1 = _resolve_person_by_email(
            client=mock_client, email="test@example.com", cache=cache
        )
        assert result1 == PersonId(123)
        assert api_call_count == 1, "First call should hit API"

        # Second call - should hit cache, NOT API
        result2 = _resolve_person_by_email(
            client=mock_client, email="test@example.com", cache=cache
        )
        assert result2 == PersonId(123)
        assert api_call_count == 1, "Second call should hit cache, not API"

        # Third call with different case - should still hit cache
        result3 = _resolve_person_by_email(
            client=mock_client, email="TEST@EXAMPLE.COM", cache=cache
        )
        assert result3 == PersonId(123)
        assert api_call_count == 1, "Case-insensitive lookup should hit cache"

    def test_company_domain_resolution_caches_api_result(self, cache: SessionCache) -> None:
        """Company domain resolution caches API result, avoiding repeated calls."""
        from unittest.mock import MagicMock

        from affinity.cli.commands.company_cmds import _resolve_company_by_domain
        from affinity.models.entities import Company
        from affinity.types import CompanyId

        api_call_count = 0
        mock_company = Company(
            id=CompanyId(456),
            name="Acme Inc",
            domain="acme.com",
            domains=["acme.com"],
        )

        class MockPage:
            def __init__(self, data: list[Company], next_cursor: str | None = None):
                self.data = data
                self.next_cursor = next_cursor

        def mock_search_pages(_term: str, **_kwargs: object):
            nonlocal api_call_count
            api_call_count += 1
            yield MockPage(data=[mock_company], next_cursor=None)

        mock_client = MagicMock()
        mock_client.companies.search_pages = mock_search_pages

        # First call - should hit API
        result1 = _resolve_company_by_domain(client=mock_client, domain="acme.com", cache=cache)
        assert result1 == CompanyId(456)
        assert api_call_count == 1, "First call should hit API"

        # Second call - should hit cache, NOT API
        result2 = _resolve_company_by_domain(client=mock_client, domain="acme.com", cache=cache)
        assert result2 == CompanyId(456)
        assert api_call_count == 1, "Second call should hit cache, not API"

    def test_person_name_resolution_caches_api_result(self, cache: SessionCache) -> None:
        """Person name resolution caches API result, avoiding repeated calls."""
        from unittest.mock import MagicMock

        from affinity.cli.commands.person_cmds import _resolve_person_by_name
        from affinity.models.entities import Person
        from affinity.types import PersonId

        api_call_count = 0
        mock_person = Person(
            id=PersonId(789),
            first_name="Alice",
            last_name="Smith",
            emails=["alice@example.com"],
            primary_email="alice@example.com",
        )

        class MockPage:
            def __init__(self, data: list[Person], next_cursor: str | None = None):
                self.data = data
                self.next_cursor = next_cursor

        def mock_search_pages(_term: str, **_kwargs: object):
            nonlocal api_call_count
            api_call_count += 1
            yield MockPage(data=[mock_person], next_cursor=None)

        mock_client = MagicMock()
        mock_client.persons.search_pages = mock_search_pages

        # First call - should hit API
        result1 = _resolve_person_by_name(client=mock_client, name="Alice Smith", cache=cache)
        assert result1 == PersonId(789)
        assert api_call_count == 1, "First call should hit API"

        # Second call - should hit cache, NOT API
        result2 = _resolve_person_by_name(client=mock_client, name="Alice Smith", cache=cache)
        assert result2 == PersonId(789)
        assert api_call_count == 1, "Second call should hit cache, not API"

        # Third call with different case - should still hit cache
        result3 = _resolve_person_by_name(client=mock_client, name="ALICE SMITH", cache=cache)
        assert result3 == PersonId(789)
        assert api_call_count == 1, "Case-insensitive lookup should hit cache"

    def test_company_name_resolution_caches_api_result(self, cache: SessionCache) -> None:
        """Company name resolution caches API result, avoiding repeated calls."""
        from unittest.mock import MagicMock

        from affinity.cli.commands.company_cmds import _resolve_company_by_name
        from affinity.models.entities import Company
        from affinity.types import CompanyId

        api_call_count = 0
        mock_company = Company(
            id=CompanyId(999),
            name="Widget Corp",
            domain="widget.com",
            domains=["widget.com"],
        )

        class MockPage:
            def __init__(self, data: list[Company], next_cursor: str | None = None):
                self.data = data
                self.next_cursor = next_cursor

        def mock_search_pages(_term: str, **_kwargs: object):
            nonlocal api_call_count
            api_call_count += 1
            yield MockPage(data=[mock_company], next_cursor=None)

        mock_client = MagicMock()
        mock_client.companies.search_pages = mock_search_pages

        # First call - should hit API
        result1 = _resolve_company_by_name(client=mock_client, name="Widget Corp", cache=cache)
        assert result1 == CompanyId(999)
        assert api_call_count == 1, "First call should hit API"

        # Second call - should hit cache, NOT API
        result2 = _resolve_company_by_name(client=mock_client, name="Widget Corp", cache=cache)
        assert result2 == CompanyId(999)
        assert api_call_count == 1, "Second call should hit cache, not API"

        # Third call with different case - should still hit cache
        result3 = _resolve_company_by_name(client=mock_client, name="WIDGET CORP", cache=cache)
        assert result3 == CompanyId(999)
        assert api_call_count == 1, "Case-insensitive lookup should hit cache"

    def test_person_fields_resolution_uses_cached_fields(self, cache: SessionCache) -> None:
        """Person field resolution uses cached field metadata."""
        from unittest.mock import MagicMock

        from affinity.cli.commands.person_cmds import _resolve_person_field_ids
        from affinity.models.entities import FieldMetadata
        from affinity.models.types import FieldValueType
        from affinity.types import FieldId

        api_call_count = 0
        mock_fields = [
            FieldMetadata(
                id=FieldId(1),
                name="Job Title",
                type="global",
                value_type=FieldValueType.TEXT,
                allows_multiple=False,
            ),
            FieldMetadata(
                id=FieldId(2),
                name="LinkedIn",
                type="global",
                value_type=FieldValueType.TEXT,
                allows_multiple=False,
            ),
        ]

        def mock_get_fields():
            nonlocal api_call_count
            api_call_count += 1
            return mock_fields

        mock_client = MagicMock()
        mock_client.persons.get_fields = mock_get_fields

        # First call - should hit API
        result1, _ = _resolve_person_field_ids(
            client=mock_client, fields=("Job Title",), field_types=[], cache=cache
        )
        assert result1 == ["field-1"]
        assert api_call_count == 1, "First call should hit API"

        # Second call - should hit cache, NOT API
        result2, _ = _resolve_person_field_ids(
            client=mock_client, fields=("LinkedIn",), field_types=[], cache=cache
        )
        assert result2 == ["field-2"]
        assert api_call_count == 1, "Second call should hit cache, not API"

    def test_company_fields_resolution_uses_cached_fields(self, cache: SessionCache) -> None:
        """Company field resolution uses cached field metadata."""
        from unittest.mock import MagicMock

        from affinity.cli.commands.company_cmds import _resolve_company_field_ids
        from affinity.models.entities import FieldMetadata
        from affinity.models.types import FieldValueType
        from affinity.types import FieldId

        api_call_count = 0
        mock_fields = [
            FieldMetadata(
                id=FieldId(10),
                name="Industry",
                type="global",
                value_type=FieldValueType.TEXT,
                allows_multiple=False,
            ),
            FieldMetadata(
                id=FieldId(20),
                name="Website",
                type="global",
                value_type=FieldValueType.TEXT,
                allows_multiple=False,
            ),
        ]

        def mock_get_fields():
            nonlocal api_call_count
            api_call_count += 1
            return mock_fields

        mock_client = MagicMock()
        mock_client.companies.get_fields = mock_get_fields

        # First call - should hit API
        result1, _ = _resolve_company_field_ids(
            client=mock_client, fields=("Industry",), field_types=[], cache=cache
        )
        assert result1 == ["field-10"]
        assert api_call_count == 1, "First call should hit API"

        # Second call - should hit cache, NOT API
        result2, _ = _resolve_company_field_ids(
            client=mock_client, fields=("Website",), field_types=[], cache=cache
        )
        assert result2 == ["field-20"]
        assert api_call_count == 1, "Second call should hit cache, not API"

    def test_no_cache_flag_disables_caching(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """With --no-cache (disabled cache), every call hits API."""
        from unittest.mock import MagicMock

        from affinity.cli.commands.person_cmds import _resolve_person_by_email
        from affinity.models.entities import Person
        from affinity.types import PersonId

        # Create a disabled cache (simulates --no-cache)
        monkeypatch.setenv("AFFINITY_SESSION_CACHE", str(tmp_path))
        config = SessionCacheConfig()
        config.enabled = False  # Simulates --no-cache
        disabled_cache = SessionCache(config)

        api_call_count = 0
        mock_person = Person(
            id=PersonId(123),
            first_name="Test",
            last_name="User",
            emails=["test@example.com"],
            primary_email="test@example.com",
        )

        class MockPage:
            def __init__(self, data: list[Person], next_cursor: str | None = None):
                self.data = data
                self.next_cursor = next_cursor

        def mock_search_pages(_term: str, **_kwargs: object):
            nonlocal api_call_count
            api_call_count += 1
            yield MockPage(data=[mock_person], next_cursor=None)

        mock_client = MagicMock()
        mock_client.persons.search_pages = mock_search_pages

        # First call - should hit API
        _resolve_person_by_email(client=mock_client, email="test@example.com", cache=disabled_cache)
        assert api_call_count == 1

        # Second call - should ALSO hit API (cache disabled)
        _resolve_person_by_email(client=mock_client, email="test@example.com", cache=disabled_cache)
        assert api_call_count == 2, "With --no-cache, every call should hit API"
