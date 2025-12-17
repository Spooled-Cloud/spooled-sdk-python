"""
gRPC module for Spooled SDK.

Note: Requires the 'grpc' extra: pip install spooled[grpc]
"""

from spooled.grpc.client import SpooledGrpcClient

__all__ = [
    "SpooledGrpcClient",
]


