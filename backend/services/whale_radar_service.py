import asyncio
import logging
from datetime import datetime, timezone
import httpx
from typing import Any

logger = logging.getLogger(__name__)

class WhaleRadarService:
    def __init__(self, timeframes: list[str] | None = None):
        self._running = False
        self._task: asyncio.Task | None = None
        self._cache = {
            "squeeze": [],
            "comprehensive": [],
            "ambush": [],
            "last_updated": None
        }
        
        # We will use an internal httpx client to fetch bapi and fapi
        self.http_client = httpx.AsyncClient(timeout=10.0)

        # Settings
        self.MIN_SIDEWAYS_DAYS = 45
        self.MAX_RANGE_PCT = 80
        self.MAX_AVG_VOL_USD = 20_000_000
        self.MIN_DATA_DAYS = 50

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._radar_loop())
        logger.info("🐳 Whale Radar Service started.")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await self.http_client.aclose()
        logger.info("🐳 Whale Radar Service stopped.")

    async def get_latest_radar_data(self) -> dict[str, Any]:
        """Returns the latest scored data from cache."""
        return self._cache

    async def _fetch_bapi_market_caps(self) -> dict[str, float]:
        """Fetches circulating market cap from Binance Spot."""
        mcap_map = {}
        try:
            resp = await self.http_client.get("https://www.binance.com/bapi/composite/v1/public/marketing/symbol/list")
            if resp.status_code == 200:
                data = resp.json().get("data", [])
                for item in data:
                    name = item.get("name", "")
                    mc = item.get("marketCap", 0)
                    if name and mc:
                        mcap_map[name] = float(mc)
        except Exception as e:
            logger.warning("Failed to fetch market caps from bapi: %s", e)
        return mcap_map

    async def _fetch_fapi(self, endpoint: str, params: dict | None = None) -> Any:
        url = f"https://fapi.binance.com{endpoint}"
        for _ in range(3):
            try:
                resp = await self.http_client.get(url, params=params)
                if resp.status_code == 200:
                    return resp.json()
                elif resp.status_code == 429:
                    await asyncio.sleep(2)
            except Exception:
                await asyncio.sleep(1)
        return None

    def _analyze_accumulation(self, symbol: str, klines: list) -> dict | None:
        if len(klines) < self.MIN_DATA_DAYS:
            return None
        
        data = []
        for k in klines:
            data.append({
                "ts": k[0],
                "open": float(k[1]),
                "high": float(k[2]),
                "low": float(k[3]),
                "close": float(k[4]),
                "vol": float(k[7]), # quote volume (USDT)
            })
        
        coin = symbol.replace("USDT", "")
        EXCLUDE = {"USDC", "USDP", "TUSD", "FDUSD", "BTCDOM", "DEFI", "USDM"}
        if coin in EXCLUDE:
            return None
            
        recent_7d = data[-7:]
        prior = data[:-7]
        if not prior:
            return None
            
        recent_avg_px = sum(d["close"] for d in recent_7d) / len(recent_7d)
        prior_avg_px = sum(d["close"] for d in prior) / len(prior)
        
        # Exclude coins that already pumped >300%
        if prior_avg_px > 0 and ((recent_avg_px - prior_avg_px) / prior_avg_px) > 3.0:
            return None
            
        best_sideways = 0
        best_range = 0
        best_avg_vol = 0
        best_slope_pct = 0
        
        for window in range(self.MIN_SIDEWAYS_DAYS, len(prior) + 1):
            window_data = prior[-window:]
            lows = [d["low"] for d in window_data]
            highs = [d["high"] for d in window_data]
            
            w_low = min(lows)
            w_high = max(highs)
            if w_low <= 0:
                continue
                
            range_pct = ((w_high - w_low) / w_low) * 100
            
            if range_pct <= self.MAX_RANGE_PCT:
                avg_vol = sum(d["vol"] for d in window_data) / len(window_data)
                if avg_vol <= self.MAX_AVG_VOL_USD:
                    closes = [d["close"] for d in window_data]
                    n = len(closes)
                    x_mean = (n - 1) / 2.0
                    y_mean = sum(closes) / n
                    num = sum((i - x_mean) * (c - y_mean) for i, c in enumerate(closes))
                    den = sum((i - x_mean) ** 2 for i in range(n))
                    slope = num / den if den > 0 else 0
                    slope_pct = (slope * n / closes[0] * 100) if closes[0] > 0 else 0
                    
                    if abs(slope_pct) > 20:
                        continue
                        
                    if window > best_sideways:
                        best_sideways = window
                        best_range = range_pct
                        best_avg_vol = avg_vol
                        best_slope_pct = slope_pct
                        
        # We allow returning partial data even if not meeting MIN_SIDEWAYS_DAYS, 
        # because the dashboard still needs a sideways score (which will just be 0).
        # Wait, the original repo completely skips them. Let's keep them if we want to show them,
        # but to save space, let's only keep them if they are somewhat interesting or just return sideways=0.
        
        days_score = min(best_sideways / 90, 1.0) * 25
        range_score = max(0, (1 - best_range / self.MAX_RANGE_PCT)) * 20 if best_range > 0 else 0
        vol_score = max(0, (1 - best_avg_vol / self.MAX_AVG_VOL_USD)) * 20 if best_avg_vol > 0 else 0
        
        recent_vol = sum(d["vol"] for d in recent_7d) / len(recent_7d)
        vol_breakout = recent_vol / best_avg_vol if best_avg_vol > 0 else 0
        
        status = "💤 Accumulating"
        if vol_breakout >= 3.0:
            status = "🔥 Breakout"
        elif vol_breakout >= 1.5:
            status = "⚡ Heating Up"

        return {
            "symbol": symbol,
            "coin": coin,
            "sideways_days": best_sideways,
            "range_pct": best_range,
            "slope_pct": best_slope_pct,
            "avg_vol": best_avg_vol,
            "current_price": data[-1]["close"],
            "recent_vol": recent_vol,
            "vol_breakout": vol_breakout,
            "status": status,
            "days_score": days_score,
        }

    async def _radar_loop(self) -> None:
        while self._running:
            try:
                logger.info("🐳 Starting Whale Radar scan cycle...")
                await self._perform_scan()
                logger.info("🐳 Whale Radar scan cycle completed.")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("🐳 Error in Whale Radar loop: %s", e, exc_info=True)
            
            # Run every 60 minutes
            await asyncio.sleep(3600)

    async def _perform_scan(self) -> None:
        # 1. Fetch market data
        exchange_info = await self._fetch_fapi("/fapi/v1/exchangeInfo")
        if not exchange_info:
            return
            
        symbols = [s["symbol"] for s in exchange_info["symbols"] 
                   if s["quoteAsset"] == "USDT" and s["contractType"] == "PERPETUAL" and s["status"] == "TRADING"]

        tickers_raw = await self._fetch_fapi("/fapi/v1/ticker/24hr")
        premiums_raw = await self._fetch_fapi("/fapi/v1/premiumIndex")
        
        if not tickers_raw or not premiums_raw:
            return

        ticker_map = {t["symbol"]: {"px_chg": float(t["priceChangePercent"]), "vol": float(t["quoteVolume"]), "price": float(t["lastPrice"])} for t in tickers_raw if t["symbol"].endswith("USDT")}
        funding_map = {p["symbol"]: float(p["lastFundingRate"]) for p in premiums_raw if p["symbol"].endswith("USDT")}
        mcap_map = await self._fetch_bapi_market_caps()

        # 2. Squeeze Hunter Strategy (Fuel)
        fuel_targets = []
        for sym, tk in ticker_map.items():
            px_chg = tk["px_chg"]
            vol = tk["vol"]
            fr = funding_map.get(sym, 0)
            coin = sym.replace("USDT", "")
            
            if px_chg > 3 and fr < -0.0003 and vol > 1_000_000:
                fuel_targets.append({
                    "symbol": sym,
                    "coin": coin,
                    "price": tk["price"],
                    "px_chg": px_chg,
                    "funding_rate": fr * 100,
                    "volume": vol,
                    "score": abs(fr) * 10000 * px_chg # Sort priority
                })
        fuel_targets.sort(key=lambda x: x["score"], reverse=True)

        # 3. Analyze Accumulation (Sideways & OI)
        comprehensive = []
        ambush = []

        for sym in symbols:
            # Add a small delay to avoid hitting Binance API rate limits too hard (2400/min limit)
            await asyncio.sleep(0.05)
            
            # Fetch 180d klines for sideways detection
            klines = await self._fetch_fapi("/fapi/v1/klines", {"symbol": sym, "interval": "1d", "limit": 180})
            if not klines or not isinstance(klines, list):
                continue
                
            acc_data = self._analyze_accumulation(sym, klines)
            if not acc_data:
                continue

            # Fetch OI History for 6h to check spikes
            oi_hist = await self._fetch_fapi("/futures/data/openInterestHist", {"symbol": sym, "period": "1h", "limit": 6})
            d6h_oi_pct = 0
            if oi_hist and len(oi_hist) >= 2:
                curr = float(oi_hist[-1]["sumOpenInterestValue"])
                prev_6h = float(oi_hist[0]["sumOpenInterestValue"])
                d6h_oi_pct = ((curr - prev_6h) / prev_6h * 100) if prev_6h > 0 else 0

            coin = acc_data["coin"]
            fr = funding_map.get(sym, 0)
            tk = ticker_map.get(sym, {"px_chg": 0, "price": 0})
            
            mcap = mcap_map.get(coin, 0)
            if mcap == 0 and oi_hist:
                circ_supply = float(oi_hist[-1].get("CMCCirculatingSupply", 0))
                mcap = circ_supply * tk["price"]
            
            # Score Components
            # Funding Score (Negative is better, Max 25)
            funding_score = min(abs(fr * 100) * 100, 25) if fr < 0 else 0
            
            # OI Score (Positive is better, Max 25)
            oi_score = min(d6h_oi_pct, 25) if d6h_oi_pct > 0 else 0
            
            # Sideways Score (Max 25)
            sideways_score = acc_data["days_score"]
            
            # Market Cap Score (Low is better, Max 25 for Comp, Max 35 for Ambush)
            comp_mcap_score = 0
            ambush_mcap_score = 0
            if 0 < mcap <= 50_000_000:
                comp_mcap_score = 25
                ambush_mcap_score = 35
            elif 0 < mcap <= 100_000_000:
                comp_mcap_score = 15
                ambush_mcap_score = 25
            elif 0 < mcap <= 200_000_000:
                comp_mcap_score = 10
                ambush_mcap_score = 15
            elif 0 < mcap <= 500_000_000:
                comp_mcap_score = 5
                ambush_mcap_score = 5

            # Total Comprehensive Score (100)
            comp_score = funding_score + comp_mcap_score + sideways_score + oi_score
            
            # Total Ambush Score (100)
            # Weights: MCAP (35), OI (30), Sideways (20), Funding (15)
            a_oi_score = min(d6h_oi_pct * 1.5, 30) if d6h_oi_pct > 0 else 0
            a_side_score = min(acc_data["sideways_days"] / 120, 1.0) * 20
            a_fund_score = min(abs(fr * 100) * 100, 15) if fr < 0 else 0
            ambush_score = ambush_mcap_score + a_oi_score + a_side_score + a_fund_score

            undercurrent = False
            if d6h_oi_pct > 3 and abs(tk["px_chg"]) < 3:
                undercurrent = True

            payload = {
                "symbol": sym,
                "coin": coin,
                "price": tk["price"],
                "px_chg": tk["px_chg"],
                "funding_rate": fr * 100,
                "oi_change_6h": d6h_oi_pct,
                "sideways_days": acc_data["sideways_days"],
                "market_cap": mcap,
                "status": acc_data["status"],
                "undercurrent": undercurrent,
                "comp_score": comp_score,
                "ambush_score": ambush_score
            }

            if comp_score > 40:
                comprehensive.append(payload)
            if ambush_score > 40:
                ambush.append(payload)

        comprehensive.sort(key=lambda x: x["comp_score"], reverse=True)
        ambush.sort(key=lambda x: x["ambush_score"], reverse=True)

        self._cache = {
            "squeeze": fuel_targets[:50],
            "comprehensive": comprehensive[:50],
            "ambush": ambush[:50],
            "last_updated": datetime.now(timezone.utc).isoformat()
        }
