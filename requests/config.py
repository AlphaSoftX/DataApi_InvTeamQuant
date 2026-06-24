from pathlib import Path
from models import Frequency


DATA_FILE_MIN_1    = Path(__file__).parent.parent / "data" / "testdata.ohlcv_minute.parquet"
DATA_FILE_DAY_1    = Path(__file__).parent.parent / "data" / "testdata.ohlcv_day.parquet"
ORDERBOOK_FILE    = Path(__file__).parent.parent / "data" / "testdata.orderbook.parquet"
RAM_LIMIT    = 500 * 1024 * 1024  # 500MB per request

# Frequencies that load from daily parquet and resample
DAILY_SOURCE_FREQS = {Frequency.DAY_1, Frequency.WEEK_1, Frequency.MONTH_1}