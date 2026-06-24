from loguru import logger
from .data_service import DataService

class DataUpdater:
    def __init__(self):
        self.data_service = DataService()

    def update_symbol(self, symbol: str, exchange: str, interval: str, source: str = "tvdatafeed"):
        """
        Updates the symbol by fetching the latest bars and merging them into the existing parquet file.
        The storage manager handles the deduplication automatically.
        """
        logger.info(f"--- Update Start: {symbol} | {exchange} | {source} ---")
        
        # We fetch a safe buffer of recent bars (e.g., 500) to ensure we overlap and catch missed bars
        # The ParquetManager handles dropping exact duplicates based on datetime.
        try:
            fetcher = self.data_service._get_fetcher(source)
            new_df = fetcher.fetch(symbol, exchange, interval, n_bars=500)
            self.data_service.storage.save_or_update(new_df, symbol, exchange)
            logger.success(f"--- Update Success: {symbol} ---")
        except Exception as e:
            logger.error(f"Update failed for {symbol}: {e}")
            raise
