import pandas as pd
from resampler import NSEResampler

# ── 1. Load your actual fetched parquet ──────────────────────────
df = pd.read_parquet("data/testdata.parquet")

print("=" * 60)
print("RAW DATA LOADED")
print("=" * 60)
print(f"Total rows     : {len(df)}")
print(f"Columns        : {list(df.columns)}")
print(f"Symbols        : {df['symbol'].unique()}")
print(f"Date range     : {df['datetime'].min()}  ->  {df['datetime'].max()}")
print(f"Timeframe check: {len(df[df['symbol'] == df['symbol'].iloc[0]])} bars for {df['symbol'].iloc[0]}")
print()

# ── 2. Pick one symbol to test ───────────────────────────────────
SYMBOL = "RELIANCE_NS"     # change if needed

rs = NSEResampler(df, symbol=SYMBOL)
print(rs)
print()

# ── 3. Resample to every timeframe and print results ─────────────
from zoneinfo import ZoneInfo
IST = ZoneInfo("Asia/Kolkata")

print(f"{'TF':>6} | {'Bars':>5} | {'First bar (IST)':^22} | {'Last bar (IST)':^22}")
print("-" * 80)

for tf in ["30min", "1H", "2H", "4H", "1D", "1W", "1M"]:
    out     = rs.resample(tf)
    ist_idx = out.index.tz_convert(IST)
    first   = ist_idx[0].strftime("%Y-%m-%d %H:%M")
    last    = ist_idx[-1].strftime("%Y-%m-%d %H:%M")
    print(f"{tf:>6} | {len(out):>5} | {first:^22} | {last:^22}")

print()

# ── 4. Print actual bar values for a spot check ──────────────────
print("=" * 60)
print(f"1H bars for {SYMBOL} (first 10):")
print("=" * 60)
df_1h = rs.resample("1H")
df_1h.index = df_1h.index.tz_convert(IST)   # show in IST for readability
print(df_1h.head(10).to_string())

print()
print("=" * 60)
print(f"1D bars for {SYMBOL} (all):")
print("=" * 60)
df_1d = rs.resample("1D")
df_1d.index = df_1d.index.tz_convert(IST)
print(df_1d.to_string())

# ── 5. Sanity checks ─────────────────────────────────────────────
print()
print("=" * 60)
print("SANITY CHECKS")
print("=" * 60)

# Check 1: 1H open should equal first 30min open of that hour
df_30 = rs.resample("30min")
df_30.index = df_30.index.tz_convert(IST)
df_1h.index = df_1h.index.tz_convert(IST)

first_1h_bar  = df_1h.index[0]
first_30_bar  = df_30.index[0]

print(f"1H  first open : {df_1h.loc[first_1h_bar, 'open']:.4f}")
print(f"30m first open : {df_30.loc[first_30_bar, 'open']:.4f}")
print(f"Match          : {df_1h.loc[first_1h_bar, 'open'] == df_30.loc[first_30_bar, 'open']}")

# Check 2: 1D volume should equal sum of all 30min volumes that day
first_day     = df_1d.index[0].date()
day_30m_bars  = df_30[df_30.index.date == first_day]
volume_30m    = day_30m_bars["volume"].sum()
volume_1d     = df_1d.iloc[0]["volume"]

print(f"\n1D  first volume (sum check) : {volume_1d:,.0f}")
print(f"30m bars volume sum          : {volume_30m:,.0f}")
print(f"Match                        : {abs(volume_1d - volume_30m) < 0.01}")

# Check 3: 1D high should be max of all 30min highs that day
high_30m = day_30m_bars["high"].max()
high_1d  = df_1d.iloc[0]["high"]
print(f"\n1D  first high (max check)   : {high_1d:.4f}")
print(f"30m bars high max            : {high_30m:.4f}")
print(f"Match                        : {abs(high_1d - high_30m) < 0.0001}")

print()
print("Done.")

# This is just a test py file to check that the resampler is working (the data is fetched from yfinance)
# Run "python test_resampler.py"