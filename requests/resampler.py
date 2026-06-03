import pandas as pd
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
UTC = ZoneInfo("UTC")

# Supported target timeframes: label -> (pandas offset, anchor offset in IST)
TARGET_TIMEFRAMES = {
    "30min": ("30min", "09:15"),
    "1H":    ("1h",    "09:15"),
    "2H":    ("2h",    "09:15"),
    "4H":    ("4h",    "09:15"),
    "1D":    ("1D",    None),
    "1W":    ("1W",    None),
    "1M":    ("1ME",   None),
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

def _to_ist(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.index = df.index.tz_convert(IST)
    return df


def _to_utc(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.index = df.index.tz_convert(UTC)
    return df


def _prepare(df: pd.DataFrame, symbol) -> pd.DataFrame:
    """
    - Filter by symbol if requested
    - Drop housekeeping columns (symbol, frequency)
    - Ensure UTC DatetimeIndex
    - Keep only present OHLCV columns
    - Sort by datetime
    """
    df = df.copy()

    if symbol and "symbol" in df.columns:
        df = df[df["symbol"] == symbol]
        if df.empty:
            raise ValueError(f"Symbol '{symbol}' not found in DataFrame.")

    df = df.drop(columns=[c for c in ("frequency", "symbol") if c in df.columns])

    if "datetime" in df.columns:
        df["datetime"] = pd.to_datetime(df["datetime"], utc=True)
        df = df.set_index("datetime")
    elif not isinstance(df.index, pd.DatetimeIndex):
        raise TypeError("DataFrame needs a DatetimeIndex or a 'datetime' column.")
    else:
        if df.index.tz is None:
            df.index = df.index.tz_localize("UTC")
        else:
            df.index = df.index.tz_convert("UTC")

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

def _resample_intraday(df: pd.DataFrame, pandas_freq: str, anchor_ist: str) -> pd.DataFrame:
    """
    Resample to 1H / 2H / 4H, anchored to 09:15 IST.
    Buckets restart fresh every trading day so cross-day drift is impossible.
    """
    agg    = _build_agg(df)
    df_ist = _to_ist(df)

    open_h, open_m      = map(int, anchor_ist.split(":"))
    open_minutes        = open_h * 60 + open_m
    bucket_size_minutes = int(pandas_freq.lower().replace("h", "")) * 60

    bar_minutes  = df_ist.index.hour * 60 + df_ist.index.minute
    bucket_index = (bar_minutes - open_minutes) // bucket_size_minutes

    date_key  = df_ist.index.normalize()
    resampled = df_ist.groupby([date_key, bucket_index]).agg(agg)

    dates, buckets = zip(*resampled.index)
    bucket_ts = pd.DatetimeIndex([
        d + pd.Timedelta(minutes=int(open_minutes + b * bucket_size_minutes))
        for d, b in zip(dates, buckets)
    ], tz=IST)
    resampled.index      = bucket_ts
    resampled.index.name = "datetime"

    return _to_utc(_drop_empty_buckets(resampled))


def _resample_daily(df: pd.DataFrame) -> pd.DataFrame:
    """One OHLCV bar per trading day, stamped at 09:15 IST."""
    agg    = _build_agg(df)
    df_ist = _to_ist(df)

    resampled            = df_ist.groupby(df_ist.index.normalize()).agg(agg)
    resampled.index.name = "datetime"
    resampled.index      = resampled.index + pd.Timedelta(hours=9, minutes=15)

    if resampled.index.tz is None:
        resampled.index = resampled.index.tz_localize(IST)

    return _to_utc(_drop_empty_buckets(resampled))


def _resample_weekly(df: pd.DataFrame) -> pd.DataFrame:
    """One OHLCV bar per ISO week, stamped at the first actual trading bar."""
    agg      = _build_agg(df)
    df_ist   = _to_ist(df)
    week_key = df_ist.index.to_series().apply(lambda dt: dt.isocalendar()[:2])

    resampled  = df_ist.groupby(week_key).agg(agg)
    first_bars = df_ist.groupby(week_key).apply(lambda g: g.index[0])

    resampled.index      = pd.DatetimeIndex(first_bars.tolist())
    resampled.index.name = "datetime"

    return _to_utc(_drop_empty_buckets(resampled))


def _resample_monthly(df: pd.DataFrame) -> pd.DataFrame:
    """
    One OHLCV bar per calendar month.
    Bar timestamp -> first actual trading bar's datetime of that month.

    Note: to_period() drops timezone info, so we strip tz before
    grouping and re-localize the result index afterward.
    """
    agg      = _build_agg(df)
    df_ist   = _to_ist(df)

    # strip tz for period grouping (pandas limitation)
    df_naive       = df_ist.copy()
    df_naive.index = df_ist.index.tz_localize(None)

    month_key  = df_naive.index.to_period("M")
    resampled  = df_naive.groupby(month_key).agg(agg)
    first_bars = df_ist.groupby(month_key).apply(lambda g: g.index[0])

    # re-attach IST timezone to the first-bar timestamps
    first_ts             = pd.DatetimeIndex(first_bars.values).tz_localize(IST)
    resampled.index      = first_ts
    resampled.index.name = "datetime"

    return _to_utc(_drop_empty_buckets(resampled))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def convert(df: pd.DataFrame, target_tf: str, symbol=None) -> pd.DataFrame:
    """
    Resample NSE 30-min OHLCV data to a lower frequency.

    Parameters
    ----------
    df        : 30-min OHLCV DataFrame; datetime can be index or column (UTC).
    target_tf : one of "30min", "1H", "2H", "4H", "1D", "1W", "1M"
    symbol    : optional symbol string to filter from a multi-symbol DataFrame

    Returns
    -------
    pd.DataFrame with UTC DatetimeIndex and OHLCV columns
    """
    if target_tf not in TARGET_TIMEFRAMES:
        raise ValueError(
            f"Unsupported timeframe '{target_tf}'. "
            f"Choose from: {list(TARGET_TIMEFRAMES.keys())}"
        )

    df = _prepare(df, symbol)
    pandas_freq, anchor = TARGET_TIMEFRAMES[target_tf]

    if target_tf == "30min":
        return df.copy()
    if target_tf in ("1H", "2H", "4H"):
        return _resample_intraday(df, pandas_freq, anchor)
    if target_tf == "1D":
        return _resample_daily(df)
    if target_tf == "1W":
        return _resample_weekly(df)
    if target_tf == "1M":
        return _resample_monthly(df)