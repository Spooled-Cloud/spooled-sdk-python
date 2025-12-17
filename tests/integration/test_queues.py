"""Integration tests for Queues resource."""

from __future__ import annotations

import os

import pytest

from spooled import SpooledClient

# Skip integration tests if no API key is set
pytestmark = pytest.mark.skipif(
    not os.environ.get("SPOOLED_API_KEY"),
    reason="SPOOLED_API_KEY not set",
)


class TestQueuesIntegration:
    """Integration tests for Queues resource."""

    def test_list_queues(self, client: SpooledClient) -> None:
        """Test listing queues."""
        queues = client.queues.list()
        assert isinstance(queues, list)

    def test_get_queue_config(self, client: SpooledClient) -> None:
        """Test getting queue config."""
        # First list to find an existing queue
        queues = client.queues.list()
        if queues:
            queue_name = queues[0].queue_name
            queue = client.queues.get(queue_name)
            assert queue.queue_name == queue_name

    def test_get_queue_stats(self, client: SpooledClient) -> None:
        """Test getting queue stats."""
        queues = client.queues.list()
        if queues:
            queue_name = queues[0].queue_name
            stats = client.queues.get_stats(queue_name)
            assert stats.queue_name == queue_name
            assert stats.pending_jobs >= 0


