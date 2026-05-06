"""Quick test to verify Binance Testnet has order/trade data."""
from binance.client import Client

c = Client(
    api_key='sjV6kOnvexvQvYylDtlU6DdKS1JElWBtQVHmo7V9tpr5mUbdRi5xzlLWJoukJcqj',
    api_secret='mE1h3QIv2lbYhoPUL0X6ql5XCAbJWtffagHC7STroCghVpMzXerfBOOsbreaQqUe',
    testnet=True,
    ping=False,
)

# Get active positions
positions = c.futures_position_information()
active = [p['symbol'] for p in positions if float(p.get('positionAmt', 0)) != 0]
print(f"Active symbols: {active}")

# Test order history for each active symbol
print("\n=== ORDER HISTORY ===")
total_orders = 0
for sym in active:
    orders = c.futures_all_orders(symbol=sym, limit=10)
    total_orders += len(orders)
    print(f"  {sym}: {len(orders)} orders")
    for o in orders[-2:]:
        print(f"    #{o['orderId']} {o['side']} {o['type']} {o['status']} qty={o['executedQty']} time={o['time']}")

print(f"\nTotal orders: {total_orders}")

# Test trade history for each active symbol
print("\n=== TRADE HISTORY ===")
total_trades = 0
for sym in active:
    trades = c.futures_my_trades(symbol=sym, limit=10)
    total_trades += len(trades)
    print(f"  {sym}: {len(trades)} trades")
    for t in trades[-2:]:
        print(f"    #{t['id']} side={t['side']} price={t['price']} qty={t['qty']} pnl={t['realizedPnl']}")

print(f"\nTotal trades: {total_trades}")

# Test income/transaction history
print("\n=== TRANSACTION HISTORY ===")
income = c.futures_income_history(limit=10)
print(f"Income entries: {len(income)}")
for i in income[:3]:
    print(f"  {i['incomeType']} {i['income']} {i['asset']} {i['symbol']} time={i['time']}")

# Test account assets
print("\n=== ASSETS ===")
acc = c.futures_account()
assets = acc.get("assets", [])
non_zero = [a for a in assets if float(a.get("walletBalance", 0)) != 0]
print(f"Non-zero assets: {len(non_zero)}")
for a in non_zero:
    print(f"  {a['asset']}: wallet={a['walletBalance']} unrealizedPnl={a['unrealizedProfit']} marginBalance={a['marginBalance']} available={a['availableBalance']}")
