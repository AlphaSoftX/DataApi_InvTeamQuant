from pydantic import BaseModel, field_validator, model_validator
from datetime import datetime
from typing import Optional
from enum import Enum
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


class Frequency(str, Enum):
    MIN_1   = "minute"
    MIN_3   = "3minute"
    MIN_5   = "5minute"
    MIN_10  = "10minute"
    MIN_15  = "15minute"
    MIN_30  = "30minute"
    MIN_45  = "45minute"
    HOUR_1  = "60minute"
    HOUR_2  = "120minute"
    HOUR_3  = "180minute"
    HOUR_4  = "240minute"
    DAY_1   = "day"
    WEEK_1  = "week"
    MONTH_1 = "month"


class DataRequest(BaseModel):
    symbols:   list[str]
    frequency: Frequency          = Frequency.DAY_1
    date_from: Optional[datetime] = None
    date_to:   Optional[datetime] = None
    bars:      Optional[int]      = None

    @field_validator("symbols")
    @classmethod
    def symbols_not_empty(cls, v):
        if not v:
            raise ValueError("symbols list cannot be empty")
        return [s.upper() for s in v]

    @field_validator("bars")
    @classmethod
    def bars_positive(cls, v):
        if v is not None and v <= 0:
            raise ValueError("bars must be a positive integer")
        return v

    @field_validator("date_from", "date_to", mode="before")
    @classmethod
    def parse_datetime(cls, v):
        if v is None:
            return v
        if isinstance(v, str):
            v = datetime.fromisoformat(v)
        if isinstance(v, datetime):
            # treat naive datetimes as IST
            if v.tzinfo is None:
                v = v.replace(tzinfo=IST)
        return v

    @model_validator(mode="after")
    def validate_time_range(self):
        has_from = self.date_from is not None
        has_to   = self.date_to is not None
        has_bars = self.bars is not None

        # format 1: date_from + date_to
        if has_from and has_to and not has_bars:
            if self.date_from >= self.date_to:
                raise ValueError("date_from must be before date_to")
            return self

        # format 2: bars only
        if has_bars and not has_from and not has_to:
            return self

        # format 3: date_from only
        if has_from and not has_to and not has_bars:
            return self

        # format 4: date_from + bars
        if has_from and has_bars and not has_to:
            return self

        # format 5: date_to + bars
        if has_to and has_bars and not has_from:
            return self

        raise ValueError(
            "invalid combination. supported formats: "
            "(1) date_from + date_to, "
            "(2) bars, "
            "(3) date_from, "
            "(4) date_from + bars, "
            "(5) date_to + bars"
        )


class SymbolData(BaseModel):
    symbol:    str
    frequency: Frequency
    bars:      list[dict]


class UnavailableInfo(BaseModel):
    symbol:       str
    reason:       str


class DataResponse(BaseModel):
    status:      str
    data:        list[SymbolData]      = []
    unavailable: list[UnavailableInfo] = []