"""Domain models (Pydantic v2)."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Granularity = Literal["hourly", "daily"]


class Location(BaseModel):
    """A geocoded location."""

    model_config = ConfigDict(frozen=True)

    name: str
    latitude: float = Field(ge=-90.0, le=90.0)
    longitude: float = Field(ge=-180.0, le=180.0)
    country: str | None = None
    timezone: str = "UTC"


class HistoryQuery(BaseModel):
    """Parameters for a history fetch."""

    model_config = ConfigDict(frozen=True)

    location: Location
    start: date
    end: date
    granularity: Granularity = "hourly"

    @model_validator(mode="after")
    def _validate_range(self) -> HistoryQuery:
        if self.end < self.start:
            raise ValueError("end date must be on or after start date")
        return self
