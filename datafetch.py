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
TV_BARS_30MIN    = 2730   # ~210 trading days of 30min bars (13 bars/day)
TV_BARS_DAILY    = 210    # ~210 trading days of daily bars

OUT_FILE = "data/testdata.parquet"

SCHEMA = pa.schema([
    ("datetime",  pa.timestamp("ns", tz="UTC")),
    ("open",      pa.float64()),
    ("high",      pa.float64()),
    ("low",       pa.float64()),
    ("close",     pa.float64()),
    ("volume",    pa.float64()),
    ("symbol",    pa.string()),
    ("frequency", pa.string()),
])

os.makedirs("data", exist_ok=True)


def fetch_tvdatafeed_30min(tv: TvDatafeed) -> list:
    frames = []
    for symbol in SYMBOLS_TV:
        print(f"Fetching {symbol} 30min from tvdatafeed...")
        df = tv.get_hist(symbol=symbol, exchange=TV_EXCHANGE,
                         interval=Interval.in_30_minute, n_bars=TV_BARS_30MIN)

        if df is None or df.empty:
            print(f"  WARNING: no data for {symbol}\n")
            continue

        df.columns    = [c.lower() for c in df.columns]
        df.index.name = "datetime"
        df            = df.reset_index()
        df["datetime"]  = pd.to_datetime(df["datetime"]).dt.tz_localize("Asia/Kolkata").dt.tz_convert("UTC")
        df["symbol"]    = f"{symbol}_NS"
        df["frequency"] = "30min"

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

        df.columns    = [c.lower() for c in df.columns]
        df.index.name = "datetime"
        df            = df.reset_index()
        df["datetime"]  = pd.to_datetime(df["datetime"]).dt.tz_localize("Asia/Kolkata").dt.tz_convert("UTC")
        df["symbol"]    = f"{symbol}_NS"
        df["frequency"] = "1d"

        frames.append(df)
        del df

    return frames


if __name__ == "__main__":
    tv = TvDatafeed()  # anonymous login, no credentials needed

    frames_30min = fetch_tvdatafeed_30min(tv)
    frames_daily = fetch_tvdatafeed_daily(tv)

    all_frames = frames_30min + frames_daily

    if not all_frames:
        print("No data fetched. Exiting.")
        exit(1)

    print("\nCombining and writing to parquet...")
    combined = pd.concat(all_frames, ignore_index=True)
    combined = combined[["datetime", "open", "high", "low", "close", "volume", "symbol", "frequency"]]
    combined = combined.sort_values(["symbol", "frequency", "datetime"]).reset_index(drop=True)

    table = pa.Table.from_pandas(combined, schema=SCHEMA, preserve_index=False)
    pq.write_table(table, OUT_FILE)

    print(f"\nTotal rows : {len(combined)}")
    print(f"Memory     : {combined.memory_usage(deep=True).sum() / 1024**2:.2f} MB")
    print(f"Saved      -> {OUT_FILE}\n")

    for (symbol, freq), group in combined.groupby(["symbol", "frequency"]):
        print(f"{symbol} [{freq}] -- {len(group)} bars | {group['datetime'].iloc[0]} -> {group['datetime'].iloc[-1]}")
    print()

    del combined, table