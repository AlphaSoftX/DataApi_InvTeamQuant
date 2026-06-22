import pandas as pd
from zoneinfo import ZoneInfo
from models import Frequency

IST = ZoneInfo("Asia/Kolkata")

MARKET_OPEN = "09:15"

# Frequency -> bucket_minutes for intraday resampling
INTRADAY_FREQS = {
    Frequency.MIN_3:  3,
    Frequency.MIN_5:  5,
    Frequency.MIN_10: 10,
    Frequency.MIN_15: 15,
    Frequency.MIN_30: 30,
    Frequency.MIN_45: 45,
    Frequency.HOUR_1: 60,
    Frequency.HOUR_2: 120,
    Frequency.HOUR_3: 180,
    Frequency.HOUR_4: 240,
}

# OHLCV aggregation rules
OHLCV_AGG = {
    "open":      "first",
    "high":      "max",
    "low":       "min",
    "close":     "last",
    "volume":    "sum",
    "adj_close": "last",    # dropped silently if absent
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _prepare(df: pd.DataFrame) -> pd.DataFrame:
    """
    - Drop housekeeping columns (symbol, frequency)
    - Set datetime column as IST-aware DatetimeIndex
    - Keep only present OHLCV columns
    - Sort by datetime
    """
    df = df.copy()
    df = df.drop(columns=[c for c in ("frequency", "symbol") if c in df.columns])
    df = df.set_index("datetime")
    df.index.name = "datetime"

    keep = [c for c in OHLCV_AGG if c in df.columns]
    df = df[keep].sort_index()

    if df.empty:
        raise ValueError("No OHLCV data left after filtering.")

    return df


def _build_agg(df: pd.DataFrame) -> dict:
    return {k: v for k, v in OHLCV_AGG.items() if k in df.columns}


def _drop_empty_buckets(df: pd.DataFrame) -> pd.DataFrame:
    ohlc_cols = [c for c in ("open", "high", "low", "close") if c in df.columns]
    return df.dropna(subset=ohlc_cols, how="all")


# ---------------------------------------------------------------------------
# Resamplers
# ---------------------------------------------------------------------------

def _resample_intraday(df: pd.DataFrame, bucket_minutes: int) -> pd.DataFrame:
    """
    Resample to any intraday frequency anchored to MARKET_OPEN IST.
    Buckets restart fresh every trading day so cross-day drift is impossible.
    Incomplete last buckets of each day are kept as-is.
    """
    agg    = _build_agg(df)

    open_h, open_m = map(int, MARKET_OPEN.split(":"))
    open_minutes   = open_h * 60 + open_m

    bar_minutes  = df.index.hour * 60 + df.index.minute
    bucket_index = (bar_minutes - open_minutes) // bucket_minutes

    date_key  = df.index.normalize()
    resampled = df.groupby([date_key, bucket_index]).agg(agg)

    dates, buckets = zip(*resampled.index)
    bucket_ts = pd.DatetimeIndex([
        d + pd.Timedelta(minutes=int(open_minutes + b * bucket_minutes))
        for d, b in zip(dates, buckets)
    ], tz=IST)
    resampled.index      = bucket_ts
    resampled.index.name = "datetime"

    return _drop_empty_buckets(resampled)


def _resample_weekly(df: pd.DataFrame) -> pd.DataFrame:
    """One OHLCV bar per ISO week, stamped at the first actual trading bar."""
    agg      = _build_agg(df)
    week_key = df.index.to_series().apply(lambda dt: dt.isocalendar()[:2])

    resampled  = df.groupby(week_key).agg(agg)
    first_bars = df.groupby(week_key).apply(lambda g: g.index[0])

    resampled.index      = pd.DatetimeIndex(first_bars.tolist())
    resampled.index.name = "datetime"

    return _drop_empty_buckets(resampled)


def _resample_monthly(df: pd.DataFrame) -> pd.DataFrame:
    """
    One OHLCV bar per calendar month, stamped at the first actual trading bar.

    Note: to_period() drops timezone info, so we strip tz before
    grouping and re-localize the result index afterward.
    """
    agg      = _build_agg(df)

    # strip tz for period grouping (pandas limitation)
    df_naive       = df.copy()
    df_naive.index = df.index.tz_localize(None)

    month_key  = df_naive.index.to_period("M")
    resampled  = df_naive.groupby(month_key).agg(agg)
    first_bars = df.groupby(month_key).apply(lambda g: g.index[0])

    # re-attach IST timezone to the first-bar timestamps
    first_ts             = pd.DatetimeIndex(first_bars.values, tz="UTC").tz_convert(IST)
    resampled.index      = first_ts
    resampled.index.name = "datetime"

    return _drop_empty_buckets(resampled)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def convert(df: pd.DataFrame, frequency: Frequency) -> pd.DataFrame:
    """
    Resample NSE 1-min or daily OHLCV data to a lower frequency.

    Parameters
    ----------
    df        : OHLCV DataFrame with a 'datetime' column (IST-aware).
                For intraday targets: provide 1-min bars.
                For weekly/monthly targets: provide daily bars.
    frequency : Frequency enum value (never called with MIN_1 or DAY_1 — those are passthroughs)

    Returns
    -------
    pd.DataFrame with IST DatetimeIndex and OHLCV columns
    """
    df = _prepare(df)

    if frequency in INTRADAY_FREQS:
        return _resample_intraday(df, INTRADAY_FREQS[frequency])
    if frequency == Frequency.WEEK_1:
        return _resample_weekly(df)
    if frequency == Frequency.MONTH_1:
        return _resample_monthly(df)

    raise ValueError(f"Unsupported frequency '{frequency}' passed to convert().")