from pathlib import Path
from models import Frequency


DATA_FILE    = Path(__file__).parent.parent / "data" / "testdata.parquet"
RAM_LIMIT    = 500 * 1024 * 1024  # 500MB per request

# Frequencies that load from daily parquet and resample
DAILY_SOURCE_FREQS = {Frequency.DAY_1, Frequency.WEEK_1, Frequency.MONTH_1}