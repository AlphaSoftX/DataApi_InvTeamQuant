from abc import ABC, abstractmethod
import pandas as pd

class BaseFetcher(ABC):
    @abstractmethod
    def fetch(self, symbol: str, exchange: str, interval: str, n_bars: int = 5000) -> pd.DataFrame:
        """
        Fetches OHLCV data and normalizes it to the standard schema:
        ['datetime', 'open', 'high', 'low', 'close', 'volume', 'symbol', 'exchange']
        Datetime must be in UTC.
        """
        pass
