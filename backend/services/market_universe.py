from __future__ import annotations

import httpx

from backend.config import Settings

SYMBOL_NAMES: dict[str, str] = {
    "BTC": "Bitcoin",
    "ETH": "Ethereum",
    "SOL": "Solana",
    "BNB": "BNB",
    "XRP": "XRP",
    "DOGE": "Dogecoin",
    "ADA": "Cardano",
    "AVAX": "Avalanche",
    "LINK": "Chainlink",
    "DOT": "Polkadot",
    "LTC": "Litecoin",
    "BCH": "Bitcoin Cash",
    "ATOM": "Cosmos",
    "TRX": "TRON",
    "NEAR": "NEAR",
    "ARB": "Arbitrum",
    "OP": "Optimism",
    "APT": "Aptos",
    "SUI": "Sui",
    "SEI": "Sei",
    "TIA": "Celestia",
    "WLD": "Worldcoin",
    "FET": "Fetch.ai",
    "RENDER": "Render",
    "INJ": "Injective",
    "UNI": "Uniswap",
    "FIL": "Filecoin",
    "LDO": "Lido DAO",
    "AAVE": "Aave",
    "DYDX": "dYdX",
    "IMX": "Immutable",
    "PEPE": "Pepe",
    "SHIB": "Shiba Inu",
    "BONK": "Bonk",
    "JUP": "Jupiter",
    "PYTH": "Pyth Network",
    "TON": "Toncoin",
    "ONDO": "Ondo",
    "WIF": "dogwifhat",
    "TAO": "Bittensor",
}

DEFAULT_SYMBOLS: list[str] = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "DOGEUSDT", "ADAUSDT",
    "AVAXUSDT", "LINKUSDT", "DOTUSDT", "LTCUSDT", "BCHUSDT", "ATOMUSDT", "TRXUSDT",
    "NEARUSDT", "ARBUSDT", "OPUSDT", "MATICUSDT", "APTUSDT", "SUIUSDT", "SEIUSDT",
    "TIAUSDT", "WLDUSDT", "FETUSDT", "RENDERUSDT", "INJUSDT", "UNIUSDT", "FILUSDT",
    "ETCUSDT", "LDOUSDT", "AAVEUSDT", "MKRUSDT", "SNXUSDT", "CRVUSDT", "DYDXUSDT",
    "IMXUSDT", "GALAUSDT", "PEPEUSDT", "SHIBUSDT", "BONKUSDT", "FLOKIUSDT", "JUPUSDT",
    "PYTHUSDT", "JTOUSDT", "MEMEUSDT", "AXLUSDT", "ALTUSDT", "BLURUSDT", "GMXUSDT",
    "ENSUSDT", "EOSUSDT", "KASUSDT", "ICPUSDT", "THETAUSDT", "RUNEUSDT", "EGLDUSDT",
    "MANAUSDT", "SANDUSDT", "APEUSDT", "CHZUSDT", "COMPUSDT", "YFIUSDT", "1INCHUSDT",
    "GMTUSDT", "ZRXUSDT", "SUSHIUSDT", "KAVAUSDT", "ZILUSDT", "ROSEUSDT", "HBARUSDT",
    "ALGOUSDT", "VETUSDT", "IOTAUSDT", "STXUSDT", "ORDIUSDT", "NEOUSDT", "QTUMUSDT",
    "XLMUSDT", "XMRUSDT", "ENJUSDT", "CFXUSDT", "NTRNUSDT", "STRKUSDT", "NOTUSDT",
    "TONUSDT", "OMUSDT", "ONDOUSDT", "BOMEUSDT", "POPCATUSDT", "WIFUSDT", "ACEUSDT",
    "NFPUSDT", "AIUSDT", "PORTALUSDT", "BEAMXUSDT", "ARKMUSDT", "PENDLEUSDT",
    "SUPERUSDT", "TURBOUSDT", "BRETTUSDT", "ETHFIUSDT", "ENAUSDT", "ZKUSDT",
    "LISTAUSDT", "BANANAUSDT", "TAOUSDT", "GRTUSDT", "SKLUSDT", "MINAUSDT",
    "ANKRUSDT", "RAYUSDT", "KSMUSDT", "CELOUSDT", "LRCUSDT", "MASKUSDT", "API3USDT",
]


class MarketUniverseService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = httpx.AsyncClient(timeout=settings.exchange_timeout_seconds)

    async def close(self) -> None:
        await self.client.aclose()

    async def get_symbols(self, limit: int | None = None) -> list[str]:
        size = limit or self.settings.universe_size
        if self.settings.demo_mode:
            return DEFAULT_SYMBOLS[:size]

        try:
            response = await self.client.get(
                f"{self.settings.binance_rest_url.rstrip('/')}/fapi/v1/ticker/24hr"
            )
            response.raise_for_status()
            payload = sorted(
                response.json(),
                key=lambda item: float(item.get('quoteVolume', 0)),
                reverse=True,
            )
            usdt_symbols = [
                item["symbol"]
                for item in payload
                if item["symbol"].endswith("USDT") and "_" not in item["symbol"]
            ]
            return usdt_symbols[:size]
        except Exception:
            return DEFAULT_SYMBOLS[:size]

    def get_name(self, symbol: str) -> str:
        base = symbol.removesuffix("USDT")
        return SYMBOL_NAMES.get(base, base.title())
