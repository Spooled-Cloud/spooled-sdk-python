"""Integration tests for Health resource."""

from __future__ import annotations

import os

import pytest

from spooled import SpooledClient

# Skip integration tests if no API key is set
pytestmark = pytest.mark.skipif(
    not os.environ.get("SPOOLED_API_KEY"),
    reason="SPOOLED_API_KEY not set",
)


class TestHealthIntegration:
    """Integration tests for Health resource."""

    def test_health_check(self, client: SpooledClient) -> None:
        """Test health check."""
        health = client.health.get()
        assert health.status in ["healthy", "degraded", "unhealthy"]

    def test_liveness_check(self, client: SpooledClient) -> None:
        """Test liveness probe."""
        is_alive = client.health.liveness()
        assert is_alive is True

    def test_readiness_check(self, client: SpooledClient) -> None:
        """Test readiness probe."""
        is_ready = client.health.readiness()
        assert isinstance(is_ready, bool)


