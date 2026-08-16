"""Canonical access to the installed Spooled SDK package version."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("spooled")
except PackageNotFoundError:  # pragma: no cover - source checkout without installed metadata
    __version__ = "1.1.0"
