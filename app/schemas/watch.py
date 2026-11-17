from datetime import datetime

from pydantic import BaseModel, Field


class WatchProviderRef(BaseModel):
    provider_id: int
    name: str
    logo_url: str | None
    priority: int


class WatchOffers(BaseModel):
    flatrate: list[WatchProviderRef] = Field(default_factory=list)
    free: list[WatchProviderRef] = Field(default_factory=list)
    ads: list[WatchProviderRef] = Field(default_factory=list)
    rent: list[WatchProviderRef] = Field(default_factory=list)
    buy: list[WatchProviderRef] = Field(default_factory=list)


class WatchAvailability(BaseModel):
    region: str
    link: str | None
    fetched_at: datetime | None
    stale: bool
    offers: WatchOffers
