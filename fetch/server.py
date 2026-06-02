from fastapi import FastAPI, Query, HTTPException
from pydantic import BaseModel
from fetch.src.services.data_service import DataService
from fetch.src.services.updater import DataUpdater
from loguru import logger
import pandas as pd

app = FastAPI(
    title="Quant Data Fetching Microservice",
    description="Production API for on-demand market data retrieval and ingestion.",
    version="1.0.0"
)

# Initialize our core engine services
service = DataService()
updater = DataUpdater()

# Define the data schema for incoming POST requests
class FetchRequest(BaseModel):
    symbol: str
    exchange: str = "NSE"
    interval: str = "30m"
    n_bars: int = 2000
    source: str = "tvdatafeed"

@app.get("/health")
def health_check():
    """Simple endpoint for load balancers to check if the microservice is alive."""
    return {"status": "healthy"}

@app.get("/data")
def get_market_data(
    symbol: str,
    exchange: str = "NSE",
    interval: str = "30m",
    n_bars: int = Query(None, description="Number of latest bars to return"),
    start_date: str = Query(None, description="YYYY-MM-DD start filter"),
    end_date: str = Query(None, description="YYYY-MM-DD end filter")
):
    """
    Exposes your local Parquet data lake via an HTTP GET request.
    Example: /data?symbol=RELIANCE&interval=30m&n_bars=100
    """
    try:
        df = service.get_data(
            symbol=symbol,
            exchange=exchange,
            interval=interval,
            start_date=start_date,
            end_date=end_date,
            n_bars=n_bars
        )
        
        # Convert the Pandas DataFrame to an easy-to-read JSON format for web clients
        return df.to_dict(orient="records")
        
    except Exception as e:
        logger.error(f"API Data Query Error: {e}")
        raise HTTPException(status_code=404, detail=str(e))

@app.post("/fetch")
def trigger_on_demand_fetch(request: FetchRequest):
    """
    Allows other systems to force an immediate on-demand data fetch and save.
    """
    try:
        service.fetch_and_store(
            symbol=request.symbol,
            exchange=request.exchange,
            interval=request.interval,
            n_bars=request.n_bars,
            source=request.source
        )
        return {"status": "success", "message": f"Successfully ingested {request.symbol}"}
    except Exception as e:
        logger.error(f"API Force Fetch Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
