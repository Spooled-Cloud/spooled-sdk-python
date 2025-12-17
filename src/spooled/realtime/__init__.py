"""
Realtime module for Spooled SDK.

Provides WebSocket and Server-Sent Events (SSE) clients for real-time
event streaming.

Note: Requires the 'realtime' extra: pip install spooled[realtime]
"""

from spooled.realtime.events import (
    PingCommand,
    RealtimeEvent,
    RealtimeEventType,
    SubscribeCommand,
    UnsubscribeCommand,
)
from spooled.realtime.sse import (
    AsyncSSEClient,
    SSEClient,
    SSEConnectionState,
)
from spooled.realtime.unified import (
    SpooledRealtime,
    SpooledRealtimeOptions,
)
from spooled.realtime.unified import (
    SubscriptionFilter as UnifiedSubscriptionFilter,
)
from spooled.realtime.websocket import (
    AsyncWebSocketClient,
    ConnectionState,
    SubscriptionFilter,
    WebSocketClient,
    WebSocketConnectionOptions,
)

__all__ = [
    # Events
    "RealtimeEvent",
    "RealtimeEventType",
    "SubscribeCommand",
    "UnsubscribeCommand",
    "PingCommand",
    # WebSocket
    "WebSocketClient",
    "AsyncWebSocketClient",
    "WebSocketConnectionOptions",
    "ConnectionState",
    "SubscriptionFilter",
    # SSE
    "SSEClient",
    "AsyncSSEClient",
    "SSEConnectionState",
    # Unified Realtime
    "SpooledRealtime",
    "SpooledRealtimeOptions",
    "UnifiedSubscriptionFilter",
]
