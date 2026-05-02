"""Exception hierarchy for weahist."""

from __future__ import annotations


class WeahistError(Exception):
    """Base exception for all weahist errors."""


class ConfigError(WeahistError):
    """Invalid or missing configuration."""


class UpstreamError(WeahistError):
    """Open-Meteo (or any upstream) returned an error or unexpected payload."""


class GeocodingError(UpstreamError):
    """Geocoding lookup failed or returned no results."""


class CacheError(WeahistError):
    """Cache read/write failure."""


class InvalidRangeError(WeahistError):
    """User-supplied date range is invalid (e.g. start > end, end in the future)."""


class RenderError(WeahistError):
    """Visualization renderer failed to produce output."""
