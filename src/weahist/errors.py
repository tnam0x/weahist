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


class RenderError(WeahistError):
    """Visualization renderer failed to produce output."""
