from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class AccountIn(BaseModel):
    api_id: int
    api_hash: str = Field(min_length=8)
    session_string: str = Field(min_length=20)


class AccountOut(BaseModel):
    connected: bool
    name: str | None = None
    username: str | None = None
    phone: str | None = None
    session_masked: str | None = None
    connected_at: datetime | None = None


class SourceIn(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    start_payload: str | None = Field(default=None, description="e.g. Prices for TGLion deep link")


class SourceUpdate(BaseModel):
    username: str | None = None
    start_payload: str | None = None
    enabled: bool | None = None


class SourceOut(BaseModel):
    id: str
    username: str
    start_payload: str | None
    enabled: bool
    status: str
    last_checked: datetime | None
    last_error: str | None


class PriceOut(BaseModel):
    source: str
    price: float
    currency: str
    updated_at: datetime


class PricesOut(BaseModel):
    country: str
    country_code: str
    calling_code: str
    cached: bool
    rows: list[PriceOut]


class SettingsIn(BaseModel):
    check_times: list[str] | None = Field(default=None, description='e.g. ["10:00", "22:00"]')
    currency: str | None = None