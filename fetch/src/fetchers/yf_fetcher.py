import pandas as pd
import yfinance as yf
from loguru import logger
from .base_fetcher import BaseFetcher
from ..exceptions import FetcherError, InvalidParameterError

class YFFetcher(BaseFetcher):
    def __init__(self):
        # YF interval format maps directly for most standard string inputs 
        # (1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo)
        pass

    def _format_symbol(self, symbol: str, exchange: str) -> str:
        # Simple heuristic mapping for Indian markets as an example
        if exchange.upper() == "NSE":
            return f"{symbol}.NS"
        elif exchange.upper() == "BSE":
            return f"{symbol}.BO"
        return symbol

    def fetch(self, symbol: str, exchange: str, interval: str, n_bars: int = 5000) -> pd.DataFrame:
        yf_symbol = self._format_symbol(symbol, exchange)
        logger.info(f"Fetching {yf_symbol} via Yahoo Finance (interval: {interval})")
        
        try:
            ticker = yf.Ticker(yf_symbol)
            # YF doesn't use exact n_bars easily without period logic, but we can fetch max/specific period
            # For intraday (like 1m, 5m) YF limits history (e.g., 7 days for 1m, 60 days for 5m/15m)
            period = "max" if interval in ["1d", "1wk", "1mo"] else "60d"
            
            df = ticker.history(period=period, interval=interval)
            
            if df.empty:
                raise FetcherError(f"No data returned for {yf_symbol}.")
            
            df = df.reset_index()
            # YF returns 'Date' or 'Datetime'
            date_col = 'Datetime' if 'Datetime' in df.columns else 'Date'
            df.rename(columns={
                date_col: 'datetime',
                'Open': 'open', 'High': 'high', 'Low': 'low', 
                'Close': 'close', 'Volume': 'volume'
            }, inplace=True)

            df['symbol'] = symbol
            df['exchange'] = exchange

            # Convert timezone to UTC
            if df['datetime'].dt.tz is None:
                df['datetime'] = df['datetime'].dt.tz_localize('UTC')
            else:
                df['datetime'] = df['datetime'].dt.tz_convert('UTC')

            # Keep only needed n_bars
            df = df.tail(n_bars)

            columns = ['datetime', 'open', 'high', 'low', 'close', 'volume', 'symbol', 'exchange']
            return df[columns]

        except Exception as e:
            logger.error(f"YFinance fetch error for {symbol}: {e}")
            raise FetcherError(str(e))
