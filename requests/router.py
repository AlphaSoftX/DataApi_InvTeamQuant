from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from fastapi import APIRouter, HTTPException, Query
from models import DataRequest, DataResponse, SymbolData, UnavailableInfo, Frequency
from loader import load_symbol
from validator import check_empty, check_range_coverage
from config import RAM_LIMIT, DAILY_SOURCE_FREQS
from resampler import convert

IST = ZoneInfo("Asia/Kolkata")

# Mock cache state
LIVE_ORDER_BOOK_STATE = {
    "738561": {  # Mock Token for RELIANCE
        "instrument_token": 738561,
        "timestamp": datetime.now(timezone.utc),
        "depth": {
            "buy": [
                {"price": 2420.50, "quantity": 500, "orders": 5},
                {"price": 2420.25, "quantity": 1100, "orders": 12},
                {"price": 2420.00, "quantity": 850, "orders": 8},
                {"price": 2419.75, "quantity": 2300, "orders": 14},
                {"price": 2419.50, "quantity": 4000, "orders": 31}
            ],
            "sell": [
                {"price": 2420.75, "quantity": 300, "orders": 2},
                {"price": 2421.00, "quantity": 1400, "orders": 9},
                {"price": 2421.25, "quantity": 900, "orders": 4},
                {"price": 2421.50, "quantity": 1950, "orders": 11},
                {"price": 2421.75, "quantity": 3500, "orders": 22}
            ]
        }
    },
    "1153601": {  # Mock Token for TCS
        "instrument_token": 1153601,
        "timestamp": datetime.now(timezone.utc),
        "depth": {
            "buy": [
                {"price": 3950.00, "quantity": 150, "orders": 2},
                {"price": 3949.50, "quantity": 420, "orders": 5}
            ],
            "sell": [
                {"price": 3950.50, "quantity": 280, "orders": 3},
                {"price": 3951.00, "quantity": 610, "orders": 7}
            ]
        }
    }
}

async def fetch_data(req: DataRequest) -> DataResponse:
    data        = []
    unavailable = []
    total_bytes = 0

    # determine which parquet frequency to load
    parquet_freq = Frequency.DAY_1 if req.frequency in DAILY_SOURCE_FREQS else Frequency.MIN_1

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

        # --- resample or passthrough ---
        if req.frequency == Frequency.MIN_1 or req.frequency == Frequency.DAY_1:
            df = df.drop(columns=["symbol", "frequency"], errors="ignore")
        else:
            df = convert(df, frequency=req.frequency)
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
        df["datetime"] = df["datetime"].dt.strftime("%Y-%m-%dT%H:%M:%S%z")

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

def parse_ist_datetime(value: str) -> datetime:
    try:
        return datetime.strptime(
            value,
            "%Y-%m-%d %H:%M:%S"
        ).replace(tzinfo=IST)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Expected format: YYYY-MM-DD HH:MM:SS"
        )

def convert_to_kite_response(resp: DataResponse) -> dict:
    if not resp.data:
        return {
            "status": "success",
            "data": {
                "candles": []
            }
        }

    symbol_data = resp.data[0]

    candles = []

    for bar in symbol_data.bars:

        candle = [
            bar["datetime"],
            bar["open"],
            bar["high"],
            bar["low"],
            bar["close"],
            bar["volume"],
        ]

        candles.append(candle)

    return {
        "status": "success",
        "data": {
            "candles": candles
        }
    }

router = APIRouter()

@router.post("/data", response_model=DataResponse)
async def post_data_endpoint(req: DataRequest):
    return await fetch_data(req)

@router.get(
    "/instruments/historical/{symbol}/{interval}"
)
async def get_data_endpoint(
    symbol: str,
    interval: Frequency,
    from_date: str = Query(alias="from"),
    to_date: str = Query(alias="to")
):
    req = DataRequest(
        symbols=[symbol],
        frequency=interval,
        date_from=parse_ist_datetime(from_date),
        date_to=parse_ist_datetime(to_date),
    )

    result = await fetch_data(req)

    return convert_to_kite_response(result)

@router.get("/quote", response_model=dict)
async def get_orderbook_endpoint(symbol: str = Query(alias="i")):
    """
    Fetches the instantaneous market depth snapshot for requested instrument tokens.
    """
    if symbol in LIVE_ORDER_BOOK_STATE:
        response_data = { symbol: LIVE_ORDER_BOOK_STATE[symbol] }
        return { "status": "success", "data": response_data }
    else:
        raise HTTPException(
            status_code=404, 
            detail=f"Instrument token {symbol} not found in active live tracking matrix."
        )