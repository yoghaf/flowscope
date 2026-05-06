from backend.services.binance_demo.binance_client import BinanceTestnetClient
from backend.config import Settings
import asyncio

async def test():
    settings = Settings()
    api_key = settings.binance_testnet_api_key
    api_secret = settings.binance_testnet_api_secret
    
    if not api_key or not api_secret:
        print("ERROR: API key/secret tidak ditemukan. Pastikan .env sudah diset.")
        print(f"API Key: '{api_key}'")
        print(f"API Secret: '{api_secret}'")
        return
    
    print(f"Menggunakan API Key: {api_key[:10]}...")
    client = BinanceTestnetClient(api_key=api_key, api_secret=api_secret)
    await client.connect()
    
    if not client.connected:
        print("ERROR: Gagal connect ke Binance Testnet")
        return
    
    print("✓ Connected to Binance Testnet\n")
    
    print('=== OPEN ORDERS ===')
    orders = await client.get_open_orders()
    print(f'Jumlah: {len(orders)}')
    for o in orders[:3]:
        print(o)
    
    print('\n=== ORDER HISTORY (BTCUSDT) ===')
    history = await client.get_order_history(symbol='BTCUSDT', limit=5)
    print(f'Jumlah: {len(history)}')
    for o in history[:3]:
        print(o)
    
    print('\n=== TRADE HISTORY (BTCUSDT) ===')
    try:
        # Coba method yang benar
        trades_manual = client.client.futures_account_trades(symbol='BTCUSDT', limit=5)
        print(f"Jumlah: {len(trades_manual)}")
        for t in trades_manual[:3]:
            print(t)
    except Exception as e:
        print(f"ERROR: {e}")

    print('\n=== POSITIONS ===')
    positions = client.client.futures_position_information()
    for p in positions:
        if float(p.get('positionAmt', 0)) != 0:
            print(p)

asyncio.run(test())
