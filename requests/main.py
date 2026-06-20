import uvicorn
from fastapi import FastAPI
from router import router, LIVE_ORDER_BOOK_STATE  # Import state mapping matrix
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import random
import asyncio

# Asynchronous background loop worker simulating real-time market depth data flow
async def simulate_live_order_book_feed():
    """Background worker modifying the shared cache state matrix to mimic market activity."""
    while True:
        for token, instrument in LIVE_ORDER_BOOK_STATE.items():
            # Choose a minor price adjustment increment step
            price_tick = random.choice([-0.05, 0.0, 0.05])
            
            # Tick Bids
            for tier in instrument["depth"]["buy"]:
                tier["price"] = round(tier["price"] + price_tick, 2)
                tier["quantity"] = max(10, tier["quantity"] + random.randint(-50, 50))
                
            # Tick Asks
            for tier in instrument["depth"]["sell"]:
                tier["price"] = round(tier["price"] + price_tick, 2)
                tier["quantity"] = max(10, tier["quantity"] + random.randint(-50, 50))
                
            instrument["timestamp"] = datetime.now(timezone.utc)
            
        # Run calculation intervals every 50ms
        await asyncio.sleep(0.05)

# Manage the application execution lifecycle states seamlessly
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup Layer: Spin up the simulator task concurrently in the background event loop
    simulator_task = asyncio.create_task(simulate_live_order_book_feed())
    yield
    # Shutdown Layer: Clean up and terminate background threads gracefully upon exit
    simulator_task.cancel()

app = FastAPI(
    title="Stock Data Api",
    lifespan=lifespan
)

app.include_router(router, prefix="")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)