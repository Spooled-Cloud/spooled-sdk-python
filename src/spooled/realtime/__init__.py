"""
Realtime module for Spooled SDK.

Provides WebSocket and Server-Sent Events (SSE) clients for real-time
event streaming.

Note: Requires the 'realtime' extra: pip install spooled[realtime]
"""

from spooled.realtime.events import (
    RealtimeEvent,
    RealtimeEventType,
    SubscribeCommand,
    UnsubscribeCommand,
    PingCommand,
)

from spooled.realtime.websocket import (
    WebSocketClient,
    AsyncWebSocketClient,
    WebSocketConnectionOptions,
    ConnectionState,
    SubscriptionFilter,
)

from spooled.realtime.sse import (
    SSEClient,
    AsyncSSEClient,
    SSEConnectionState,
)

from spooled.realtime.unified import (
    SpooledRealtime,
    SpooledRealtimeOptions,
    SubscriptionFilter as UnifiedSubscriptionFilter,
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
