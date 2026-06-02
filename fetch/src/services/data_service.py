from loguru import logger
from ..fetchers.tv_fetcher import TVFetcher
from ..fetchers.yf_fetcher import YFFetcher
from ..storage.parquet_manager import ParquetManager
from ..exceptions import InvalidParameterError

class DataService:
    def __init__(self):
        self.fetchers = {
            "tvdatafeed": TVFetcher(),
            "yfinance": YFFetcher()
        }
        self.storage = ParquetManager()

    def _get_fetcher(self, source: str):
        source = source.lower()
        if source not in self.fetchers:
            raise InvalidParameterError(f"Source '{source}' not supported.")
        return self.fetchers[source]

    def fetch_and_store(self, symbol: str, exchange: str, interval: str, n_bars: int = 5000, source: str = "tvdatafeed"):
        logger.info(f"--- Fetch Start: {symbol} | {exchange} | {interval} | {source} ---")
        fetcher = self._get_fetcher(source)
        
        df = fetcher.fetch(symbol, exchange, interval, n_bars)
        self.storage.save_or_update(df, symbol, exchange)
        logger.success(f"--- Fetch Success: {symbol} ---")

    def get_data(self, symbol: str, exchange: str, interval: str, start_date=None, end_date=None, n_bars=None):
        logger.info(f"Querying local data: {symbol} | {exchange}")
        return self.storage.load(symbol, exchange, start_date, end_date, n_bars)
