import os
import pyarrow as pa
import pyarrow.parquet as pq
import pandas as pd
from tvDatafeed import TvDatafeed, Interval

# --- config ---
SYMBOLS_TV = [
    "RELIANCE", "TCS", "INFY", "HDFCBANK",
    "ICICIBANK", "SBIN", "WIPRO", "BAJFINANCE",
    "AXISBANK", "KOTAKBANK"
]

TV_EXCHANGE      = "NSE"
TV_BARS_MIN_1    = 150 * 375  # ~150 days of 1min bars (6:15 hrs/day)
TV_BARS_DAILY    = 150        # 150 daily bars

OUT_FILE_MIN_1 = "data/testdata.ohlcv_minute.parquet"
OUT_FILE_DAY_1 = "data/testdata.ohlcv_day.parquet"

SCHEMA = pa.schema([
    ("datetime", pa.timestamp("ns", tz="Asia/Kolkata")),
    ("open",     pa.float64()),
    ("high",     pa.float64()),
    ("low",      pa.float64()),
    ("close",    pa.float64()),
    ("volume",   pa.float64()),
    ("symbol",   pa.string()),
])

os.makedirs("data", exist_ok=True)


def fetch_tvdatafeed_1min(tv: TvDatafeed) -> list:
    frames = []
    for symbol in SYMBOLS_TV:
        print(f"Fetching {symbol} 1min from tvdatafeed...")
        df = tv.get_hist(symbol=symbol, exchange=TV_EXCHANGE,
                         interval=Interval.in_1_minute, n_bars=TV_BARS_MIN_1)

        if df is None or df.empty:
            print(f"  WARNING: no data for {symbol}\n")
            continue

        df.columns     = [c.lower() for c in df.columns]
        df.index.name  = "datetime"
        df             = df.reset_index()
        df["datetime"] = pd.to_datetime(df["datetime"]).dt.tz_localize("Asia/Kolkata")
        df["symbol"]   = f"{symbol}_NS"

        frames.append(df)
        del df

    return frames


def fetch_tvdatafeed_daily(tv: TvDatafeed) -> list:
    frames = []
    for symbol in SYMBOLS_TV:
        print(f"Fetching {symbol} 1d from tvdatafeed...")
        df = tv.get_hist(symbol=symbol, exchange=TV_EXCHANGE,
                         interval=Interval.in_daily, n_bars=TV_BARS_DAILY)

        if df is None or df.empty:
            print(f"  WARNING: no data for {symbol}\n")
            continue

        df.columns     = [c.lower() for c in df.columns]
        df.index.name  = "datetime"
        df             = df.reset_index()
        df["datetime"] = pd.to_datetime(df["datetime"]).dt.tz_localize("Asia/Kolkata")
        df["symbol"]   = f"{symbol}_NS"

        frames.append(df)
        del df

    return frames


def write_parquet(frames: list, out_file: str, label: str) -> None:
    if not frames:
        print(f"No {label} data fetched, skipping.")
        return

    print(f"\nCombining and writing {label} data to parquet...")
    combined = pd.concat(frames, ignore_index=True)
    combined = combined[["datetime", "open", "high", "low", "close", "volume", "symbol"]]
    combined = combined.sort_values(["symbol", "datetime"]).reset_index(drop=True)

    table = pa.Table.from_pandas(combined, schema=SCHEMA, preserve_index=False)
    pq.write_table(table, out_file)

    print(f"Total rows : {len(combined)}")
    print(f"Memory     : {combined.memory_usage(deep=True).sum() / 1024**2:.2f} MB")
    print(f"Saved      -> {out_file}\n")

    for symbol, group in combined.groupby("symbol"):
        print(f"  {symbol} -- {len(group)} bars | {group['datetime'].iloc[0]} -> {group['datetime'].iloc[-1]}")
    print()

    del combined, table


if __name__ == "__main__":
    tv = TvDatafeed()  # anonymous login, no credentials needed

    write_parquet(fetch_tvdatafeed_1min(tv),  OUT_FILE_MIN_1, "1min")
    write_parquet(fetch_tvdatafeed_daily(tv), OUT_FILE_DAY_1, "daily")