import pandas as pd
from loguru import logger
from tvDatafeed import TvDatafeed, Interval
from .base_fetcher import BaseFetcher
from ..exceptions import FetcherError, InvalidParameterError

class TVFetcher(BaseFetcher):
    def __init__(self):
        # Initializes in guest mode
        try:
            self.tv = TvDatafeed()
        except Exception as e:
            logger.error(f"Failed to initialize TVDatafeed: {e}")
            raise FetcherError(f"TVDatafeed init failed: {e}")

        self.interval_map = {
            "1m": Interval.in_1_minute,
            "3m": Interval.in_3_minute,
            "5m": Interval.in_5_minute,
            "15m": Interval.in_15_minute,
            "30m": Interval.in_30_minute,
            "1h": Interval.in_1_hour,
            "2h": Interval.in_2_hour,
            "4h": Interval.in_4_hour,
            "1d": Interval.in_daily,
            "1w": Interval.in_weekly,
            "1M": Interval.in_monthly,
        }

    def fetch(self, symbol: str, exchange: str, interval: str, n_bars: int = 5000) -> pd.DataFrame:
        logger.info(f"Fetching {symbol} from {exchange} via TVDatafeed (interval: {interval})")
        
        if interval not in self.interval_map:
            raise InvalidParameterError(f"Invalid interval '{interval}' for TVDatafeed.")

        try:
            df = self.tv.get_hist(
                symbol=symbol,
                exchange=exchange,
                interval=self.interval_map[interval],
                n_bars=n_bars
            )
            
            if df is None or df.empty:
                raise FetcherError(f"No data returned for {symbol} on {exchange}.")

            # Reset index to get datetime as a column
            df = df.reset_index()
            df.rename(columns={'datetime': 'datetime'}, inplace=True)
            
            # Normalize schema
            df['symbol'] = symbol
            df['exchange'] = exchange
            
            # Convert timezone to UTC
            if df['datetime'].dt.tz is None:
                df['datetime'] = df['datetime'].dt.tz_localize('UTC')
            else:
                df['datetime'] = df['datetime'].dt.tz_convert('UTC')

            # Ensure strict column ordering
            columns = ['datetime', 'open', 'high', 'low', 'close', 'volume', 'symbol', 'exchange']
            return df[columns]
            
        except Exception as e:
            logger.error(f"TVDatafeed fetch error for {symbol}: {e}")
            raise FetcherError(str(e))
