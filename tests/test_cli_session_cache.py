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
