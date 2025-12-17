"""Unit tests for configuration module."""

from __future__ import annotations

import pytest
from pydantic import ValidationError as PydanticValidationError

from spooled.config import (
    API_BASE_PATH,
    DEFAULT_BASE_URL,
    DEFAULT_GRPC_ADDRESS,
    DEFAULT_TIMEOUT,
    DEFAULT_USER_AGENT,
    CircuitBreakerConfig,
    RetryConfig,
    SpooledClientConfig,
    resolve_config,
    validate_config,
)


class TestRetryConfig:
    """Tests for RetryConfig."""

    def test_default_values(self) -> None:
        """Test default retry config values."""
        config = RetryConfig()
        assert config.max_retries == 3
        assert config.base_delay == 1.0
        assert config.max_delay == 30.0
        assert config.factor == 2.0
        assert config.jitter is True

    def test_custom_values(self) -> None:
        """Test custom retry config values."""
        config = RetryConfig(
            max_retries=5,
            base_delay=0.5,
            max_delay=60.0,
            factor=3.0,
            jitter=False,
        )
        assert config.max_retries == 5
        assert config.base_delay == 0.5
        assert config.max_delay == 60.0
        assert config.factor == 3.0
        assert config.jitter is False

    def test_max_retries_validation(self) -> None:
        """Test max_retries validation bounds."""
        # Valid bounds
        RetryConfig(max_retries=0)
        RetryConfig(max_retries=10)

        # Invalid: negative
        with pytest.raises(PydanticValidationError):
            RetryConfig(max_retries=-1)

        # Invalid: too high
        with pytest.raises(PydanticValidationError):
            RetryConfig(max_retries=11)

    def test_base_delay_validation(self) -> None:
        """Test base_delay must be positive."""
        with pytest.raises(PydanticValidationError):
            RetryConfig(base_delay=0)

        with pytest.raises(PydanticValidationError):
            RetryConfig(base_delay=-1)

    def test_factor_validation(self) -> None:
        """Test factor must be > 1."""
        with pytest.raises(PydanticValidationError):
            RetryConfig(factor=1.0)

        with pytest.raises(PydanticValidationError):
            RetryConfig(factor=0.5)

    def test_frozen(self) -> None:
        """Test config is frozen (immutable)."""
        config = RetryConfig()
        with pytest.raises(PydanticValidationError):
            config.max_retries = 10


class TestCircuitBreakerConfig:
    """Tests for CircuitBreakerConfig."""

    def test_default_values(self) -> None:
        """Test default circuit breaker config values."""
        config = CircuitBreakerConfig()
        assert config.enabled is True
        assert config.failure_threshold == 5
        assert config.success_threshold == 3
        assert config.timeout == 30.0

    def test_disabled(self) -> None:
        """Test circuit breaker can be disabled."""
        config = CircuitBreakerConfig(enabled=False)
        assert config.enabled is False

    def test_threshold_validation(self) -> None:
        """Test threshold validation."""
        # Valid
        CircuitBreakerConfig(failure_threshold=1, success_threshold=1)

        # Invalid: zero or negative
        with pytest.raises(PydanticValidationError):
            CircuitBreakerConfig(failure_threshold=0)

        with pytest.raises(PydanticValidationError):
            CircuitBreakerConfig(success_threshold=0)

    def test_timeout_validation(self) -> None:
        """Test timeout must be positive."""
        with pytest.raises(PydanticValidationError):
            CircuitBreakerConfig(timeout=0)

        with pytest.raises(PydanticValidationError):
            CircuitBreakerConfig(timeout=-10)


class TestSpooledClientConfig:
    """Tests for SpooledClientConfig."""

    def test_default_values(self) -> None:
        """Test default client config values."""
        config = SpooledClientConfig(api_key="sk_test_xxxxxxxxxxxxxxxxxxxx")
        assert config.base_url == DEFAULT_BASE_URL
        assert config.grpc_address == DEFAULT_GRPC_ADDRESS
        assert config.timeout == DEFAULT_TIMEOUT
        assert config.user_agent == DEFAULT_USER_AGENT
        assert config.auto_refresh_token is True
        assert config.debug is False

    def test_api_key_min_length(self) -> None:
        """Test API key minimum length validation."""
        # Valid: exactly 10 characters
        SpooledClientConfig(api_key="1234567890")

        # Invalid: too short
        with pytest.raises(PydanticValidationError):
            SpooledClientConfig(api_key="123456789")

    def test_no_auth_is_allowed(self) -> None:
        """Test config can be created without auth (validated later)."""
        # This is allowed at config level, validated at resolve
        config = SpooledClientConfig()
        assert config.api_key is None
        assert config.access_token is None

    def test_custom_base_url(self) -> None:
        """Test custom base URL."""
        config = SpooledClientConfig(
            api_key="sk_test_xxxxxxxxxxxxxxxxxxxx",
            base_url="https://custom.api.com",
        )
        assert config.base_url == "https://custom.api.com"

    def test_custom_timeout(self) -> None:
        """Test custom timeout values."""
        config = SpooledClientConfig(
            api_key="sk_test_xxxxxxxxxxxxxxxxxxxx",
            timeout=60.0,
            connect_timeout=5.0,
        )
        assert config.timeout == 60.0
        assert config.connect_timeout == 5.0

    def test_timeout_validation(self) -> None:
        """Test timeout must be positive."""
        with pytest.raises(PydanticValidationError):
            SpooledClientConfig(
                api_key="sk_test_xxxxxxxxxxxxxxxxxxxx",
                timeout=0,
            )

    def test_custom_headers(self) -> None:
        """Test custom headers."""
        config = SpooledClientConfig(
            api_key="sk_test_xxxxxxxxxxxxxxxxxxxx",
            headers={"X-Custom-Header": "value"},
        )
        assert config.headers == {"X-Custom-Header": "value"}

    def test_extra_fields_forbidden(self) -> None:
        """Test extra fields are not allowed."""
        with pytest.raises(PydanticValidationError):
            SpooledClientConfig(
                api_key="sk_test_xxxxxxxxxxxxxxxxxxxx",
                unknown_field="value",
            )

    def test_get_ws_url_from_https(self) -> None:
        """Test WebSocket URL derivation from HTTPS."""
        config = SpooledClientConfig(
            api_key="sk_test_xxxxxxxxxxxxxxxxxxxx",
            base_url="https://api.example.com",
        )
        assert config.get_ws_url() == "wss://api.example.com"

    def test_get_ws_url_from_http(self) -> None:
        """Test WebSocket URL derivation from HTTP."""
        config = SpooledClientConfig(
            api_key="sk_test_xxxxxxxxxxxxxxxxxxxx",
            base_url="http://localhost:8080",
        )
        assert config.get_ws_url() == "ws://localhost:8080"

    def test_get_ws_url_custom(self) -> None:
        """Test custom WebSocket URL."""
        config = SpooledClientConfig(
            api_key="sk_test_xxxxxxxxxxxxxxxxxxxx",
            ws_url="wss://ws.example.com",
        )
        assert config.get_ws_url() == "wss://ws.example.com"


class TestResolveConfig:
    """Tests for resolve_config function."""

    def test_basic_resolution(self) -> None:
        """Test basic config resolution."""
        config = SpooledClientConfig(api_key="sk_test_xxxxxxxxxxxxxxxxxxxx")
        resolved = resolve_config(config)

        assert resolved.api_key == "sk_test_xxxxxxxxxxxxxxxxxxxx"
        assert resolved.base_url == DEFAULT_BASE_URL.rstrip("/")
        assert resolved.ws_url.startswith("wss://")
        assert resolved.debug_fn is None

    def test_debug_mode(self) -> None:
        """Test debug mode enables debug function."""
        config = SpooledClientConfig(
            api_key="sk_test_xxxxxxxxxxxxxxxxxxxx",
            debug=True,
        )
        resolved = resolve_config(config)

        assert resolved.debug_fn is not None
        # Test debug function works
        resolved.debug_fn("test message", {"key": "value"})
        resolved.debug_fn("test message", None)

    def test_strips_trailing_slash(self) -> None:
        """Test trailing slashes are stripped from URLs."""
        config = SpooledClientConfig(
            api_key="sk_test_xxxxxxxxxxxxxxxxxxxx",
            base_url="https://api.example.com/",
        )
        resolved = resolve_config(config)

        assert resolved.base_url == "https://api.example.com"


class TestValidateConfig:
    """Tests for validate_config function."""

    def test_valid_api_key(self) -> None:
        """Test validation passes with API key."""
        config = SpooledClientConfig(api_key="sk_test_xxxxxxxxxxxxxxxxxxxx")
        resolved = resolve_config(config)
        validate_config(resolved)  # Should not raise

    def test_valid_access_token(self) -> None:
        """Test validation passes with access token."""
        config = SpooledClientConfig(access_token="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9")
        resolved = resolve_config(config)
        validate_config(resolved)  # Should not raise

    def test_missing_auth_raises(self) -> None:
        """Test validation fails without any auth."""
        config = SpooledClientConfig()
        resolved = resolve_config(config)

        with pytest.raises(ValueError, match="Either api_key or access_token must be provided"):
            validate_config(resolved)

    def test_admin_key_alone_not_sufficient(self) -> None:
        """Test admin key alone is not sufficient for auth."""
        config = SpooledClientConfig(admin_key="admin_xxxx")
        resolved = resolve_config(config)

        with pytest.raises(ValueError, match="Either api_key or access_token"):
            validate_config(resolved)


class TestConstants:
    """Tests for configuration constants."""

    def test_default_base_url(self) -> None:
        """Test default base URL."""
        assert DEFAULT_BASE_URL == "https://api.spooled.cloud"

    def test_api_base_path(self) -> None:
        """Test API base path."""
        assert API_BASE_PATH == "/api/v1"

    def test_default_timeout(self) -> None:
        """Test default timeout is reasonable."""
        assert DEFAULT_TIMEOUT == 30.0

    def test_default_user_agent(self) -> None:
        """Test default user agent contains sdk name."""
        assert "spooled-python" in DEFAULT_USER_AGENT


