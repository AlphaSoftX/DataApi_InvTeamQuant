import requests
import pandas as pd
import io
import concurrent.futures
import time
import random
from fetch.src.services.data_service import DataService
from fetch.src.services.updater import DataUpdater
from loguru import logger

def fetch_nifty_500_symbols():
    url = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    logger.info("Fetching live Nifty 500 symbol list from NSE...")
    response = requests.get(url, headers=headers, timeout=10)
    
    if response.status_code != 200:
        logger.error(f"Failed to fetch Nifty 500 list. Status Code: {response.status_code}")
        raise ConnectionError("Could not connect to NSE.")
        
    df = pd.read_csv(io.StringIO(response.text))
    symbols = df['Symbol'].tolist()
    logger.success(f"Successfully loaded {len(symbols)} symbols from NSE.")
    return symbols

def process_symbol(symbol: str, exchange: str, interval: str):
    """Worker function to process a single stock with a polite delay."""
    # The polite delay: wait a random time between 1 and 3 seconds before hitting the API
    time.sleep(random.uniform(1.0, 3.0))
    
    service = DataService()
    updater = DataUpdater()
    
    try:
        logger.info(f"Attempting to update {symbol}...")
        updater.update_symbol(symbol, exchange, interval)
    except Exception:
        logger.info(f"No existing data for {symbol}. Running initial fetch...")
        try:
            service.fetch_and_store(symbol, exchange, interval, n_bars=2000)
        except Exception as e:
            logger.error(f"Failed to process {symbol}: {e}")

def main():
    logger.info("=== Starting Mass Quant Data Fetch ===")
    
    try:
        stock_list = fetch_nifty_500_symbols()
    except Exception as e:
        logger.critical(f"Aborting execution: {e}")
        return

    exchange = "NSE"
    interval = "30m"

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = [
            executor.submit(process_symbol, stock, exchange, interval) 
            for stock in stock_list
        ]
        concurrent.futures.wait(futures)

    logger.success("=== Mass Fetch Complete ===")

if __name__ == "__main__":
    main()
