import asyncio
import logging
from backend.services.signal_service import SignalService
from backend.config import get_settings

logging.basicConfig(level=logging.INFO)

async def test():
    settings = get_settings()
    service = SignalService(settings)
    print("Starting service...")
    # Just start and stop
    await asyncio.sleep(2)
    print("Service ok")

if __name__ == "__main__":
    try:
        asyncio.run(test())
    except Exception as e:
        print(f"Error: {e}")
