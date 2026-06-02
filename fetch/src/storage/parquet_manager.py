import pandas as pd
from pathlib import Path
from loguru import logger
from ..exceptions import StorageError

class ParquetManager:
    def __init__(self, data_dir: str = "data/raw"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _get_filepath(self, symbol: str, exchange: str) -> Path:
        return self.data_dir / f"{exchange}_{symbol}.parquet"

    def save_or_update(self, df: pd.DataFrame, symbol: str, exchange: str):
        filepath = self._get_filepath(symbol, exchange)
        
        try:
            if filepath.exists():
                logger.info(f"Existing parquet found for {symbol}. Appending new data.")
                existing_df = pd.read_parquet(filepath)
                combined_df = pd.concat([existing_df, df])
                
                # Deduplicate and sort
                combined_df.drop_duplicates(subset=['datetime'], keep='last', inplace=True)
                combined_df.sort_values('datetime', inplace=True)
                combined_df.to_parquet(filepath, engine='pyarrow')
                logger.success(f"Updated {filepath.name} successfully. Total rows: {len(combined_df)}")
            else:
                df.sort_values('datetime', inplace=True)
                df.to_parquet(filepath, engine='pyarrow')
                logger.success(f"Created {filepath.name} successfully. Total rows: {len(df)}")
        except Exception as e:
            logger.error(f"Failed to save parquet for {symbol}: {e}")
            raise StorageError(f"Parquet save error: {e}")

    def load(self, symbol: str, exchange: str, start_date=None, end_date=None, n_bars=None) -> pd.DataFrame:
        filepath = self._get_filepath(symbol, exchange)
        
        if not filepath.exists():
            raise StorageError(f"No local data found for {exchange}_{symbol}.")
        
        try:
            df = pd.read_parquet(filepath)
            
            if start_date:
                start_date = pd.to_datetime(start_date, utc=True)
                df = df[df['datetime'] >= start_date]
            if end_date:
                end_date = pd.to_datetime(end_date, utc=True)
                df = df[df['datetime'] <= end_date]
            if n_bars:
                df = df.tail(n_bars)
                
            return df
        except Exception as e:
            logger.error(f"Failed to read parquet for {symbol}: {e}")
            raise StorageError(f"Parquet read error: {e}")
            
    def get_latest_timestamp(self, symbol: str, exchange: str):
        """Helper to get the last recorded timestamp to optimize fetches if needed."""
        filepath = self._get_filepath(symbol, exchange)
        if not filepath.exists():
            return None
        df = pd.read_parquet(filepath, columns=['datetime'])
        return df['datetime'].max()
