from fastapi import APIRouter
from models import DataRequest, DataResponse, SymbolData, UnavailableInfo, Frequency
from loader import load_symbol
from validator import check_empty, check_range_coverage
from config import RAM_LIMIT, FREQUENCY_TO_TF
from resampler import convert

router = APIRouter()

# frequencies that use stored daily bars from parquet
DAILY_SOURCE_FREQS = {Frequency.DAY_1, Frequency.WEEK_1, Frequency.MONTH_1}


@router.post("/data", response_model=DataResponse)
async def get_data(req: DataRequest):
    data        = []
    unavailable = []
    total_bytes = 0
    target_tf   = FREQUENCY_TO_TF[req.frequency]

    # determine which parquet frequency to load
    parquet_freq = "1d" if req.frequency in DAILY_SOURCE_FREQS else "30min"

    for symbol in req.symbols:

        df, unavailable_reason, avail_from, avail_to = load_symbol(
            symbol       = symbol,
            parquet_freq = parquet_freq,
            date_from    = req.date_from,
            date_to      = req.date_to,
            bars         = req.bars,
        )

        # --- boundary not found ---
        if unavailable_reason:
            unavailable.append(UnavailableInfo(symbol=symbol, reason=unavailable_reason))
            continue

        # --- symbol completely missing or range not available ---
        if df is None:
            unavailable.append(check_empty(symbol, avail_from, avail_to))
            continue

        # --- resample if needed ---
        if req.frequency == Frequency.DAY_1 or req.frequency == Frequency.MIN_30:
            # use stored daily bars / 30min bars directly, just drop non-OHLCV columns
            df = df.drop(columns=["symbol", "frequency"], errors="ignore")
        else:
            # resample 30min bars to 1h/2h/4h
            df = convert(df, target_tf=target_tf, symbol=None)
            df = df.reset_index()

        # --- range coverage check (formats 1 and 3, on resampled data) ---
        coverage_issue = check_range_coverage(symbol, avail_from, avail_to, req)
        if coverage_issue:
            unavailable.append(coverage_issue)
            continue

        # --- bars-based formats: validate count and trim after resampling ---
        if req.bars:
            if len(df) < req.bars:
                unavailable.append(UnavailableInfo(
                    symbol = symbol,
                    reason = (
                        f"not enough history for {symbol}: requested {req.bars} {req.frequency.value} bars "
                        f"but only {len(df)} available, use fetch service to get missing data"
                    )
                ))
                continue

            if req.date_from and not req.date_to:
                # format 4: first N bars from date_from
                df = df.iloc[:req.bars]
            else:
                # format 2: latest N bars, format 5: last N bars before date_to
                df = df.iloc[-req.bars:]

        # --- format datetime for output ---
        # df["datetime"] = df["datetime"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        df["datetime"] = (
            df["datetime"]
            .dt.tz_convert("Asia/Kolkata")
            .dt.strftime("%Y-%m-%dT%H:%M:%S%z")
        )

        # --- RAM check on final resampled data ---
        total_bytes += df.memory_usage(deep=True).sum()
        if total_bytes > RAM_LIMIT:
            remaining = [s for s in req.symbols if s not in {sd.symbol for sd in data} and s != symbol]
            unavailable.append(UnavailableInfo(
                symbol = symbol,
                reason = "request RAM limit reached, please request fewer symbols or a smaller date range"
            ))
            for s in remaining:
                unavailable.append(UnavailableInfo(
                    symbol = s,
                    reason = "skipped due to request RAM limit"
                ))
            break

        data.append(SymbolData(
            symbol    = symbol,
            frequency = req.frequency,
            bars      = df.to_dict(orient="records")
        ))

    status = "ok"          if data and not unavailable else \
             "partial"     if data and unavailable     else \
             "unavailable"

    return DataResponse(
        status      = status,
        data        = data,
        unavailable = unavailable,
    )