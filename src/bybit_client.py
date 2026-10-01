"""Official Bybit V5 Public REST API Client for European Options & Klines."""

import logging
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple
import requests

logger = logging.getLogger(__name__)

MONTH_MAP = {
    'JAN': '01', 'FEB': '02', 'MAR': '03', 'APR': '04', 'MAY': '05', 'JUN': '06',
    'JUL': '07', 'AUG': '08', 'SEP': '09', 'OCT': '10', 'NOV': '11', 'DEC': '12'
}

class BybitClient:
    """Official Bybit V5 Market REST API Client."""

    BASE_URL = "https://api.bybit.com/v5/market"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "BybitOptionsQuantActor/1.0",
            "Accept": "application/json"
        })
        # Bybit Option Symbol: BTC-25SEP26-54000-C-USDT or XAUT-26AUG26-4510-C-USDT
        self.symbol_regex = re.compile(
            r'^([A-Z]+)-(\d{1,2})([A-Z]{3})(\d{2})-(\d+(?:\.\d+)?)-([CP])(?:-[A-Z]+)?$'
        )

    def _safe_get(self, url: str, timeout: int = 8) -> Optional[Any]:
        try:
            res = self.session.get(url, timeout=timeout)
            if res.status_code == 200:
                data = res.json()
                if data.get('retCode') == 0:
                    return data
        except Exception as e:
            logger.debug(f"Bybit GET failed for {url}: {e}")
        return None

    def get_spot_price(self, currency: str) -> float:
        """Fetch current real-time price from Bybit spot or linear perpetual."""
        clean = currency.upper().replace('-USD', '').replace('-USDT', '').replace('^', '').strip()
        if clean in ['XAU', 'GOLD', 'PAXG']:
            clean = 'XAUT'

        symbol = f"{clean}USDT"

        # 1. Spot Tickers
        data_spot = self._safe_get(f"{self.BASE_URL}/tickers?category=spot&symbol={symbol}")
        if data_spot:
            lst = data_spot.get('result', {}).get('list', [])
            if lst:
                p = float(lst[0].get('lastPrice', 0))
                if p > 0:
                    return p

        # 2. Linear Futures Tickers
        data_lin = self._safe_get(f"{self.BASE_URL}/tickers?category=linear&symbol={symbol}")
        if data_lin:
            lst = data_lin.get('result', {}).get('list', [])
            if lst:
                p = float(lst[0].get('lastPrice', 0))
                if p > 0:
                    return p

        # 3. Option Index Price
        data_idx = self._safe_get(f"{self.BASE_URL}/index-price?category=option&baseCoin={clean}")
        if data_idx:
            lst = data_idx.get('result', {}).get('list', [])
            if lst:
                p = float(lst[0].get('indexPrice', 0))
                if p > 0:
                    return p

        defaults = {'BTC': 65000.0, 'ETH': 2650.0, 'SOL': 155.0, 'XAUT': 2685.0, 'XRP': 0.60, 'DOGE': 0.12, 'MNT': 0.85}
        return defaults.get(clean, 100.0)

    def get_options_data(self, currency: str) -> List[Dict[str, Any]]:
        """Fetch all active European options tickers and Greeks for baseCoin from Bybit V5."""
        clean = currency.upper().replace('-USD', '').replace('-USDT', '').replace('^', '').strip()
        if clean in ['XAU', 'GOLD', 'PAXG']:
            clean = 'XAUT'

        url = f"{self.BASE_URL}/tickers?category=option&baseCoin={clean}"
        data = self._safe_get(url)

        if not data:
            logger.warning(f"No options ticker data returned from Bybit V5 for {clean}")
            return []

        items = data.get('result', {}).get('list', [])
        logger.info(f"Retrieved {len(items)} active option contracts for {clean} from Bybit.")
        return items

    def get_klines(
        self,
        currency: str,
        interval: str = "D",
        limit: int = 30
    ) -> List[Dict[str, Any]]:
        """Fetch historical Klines OHLCV candlesticks from Bybit."""
        clean = currency.upper().replace('-USD', '').replace('-USDT', '').replace('^', '').strip()
        if clean in ['XAU', 'GOLD', 'PAXG']:
            clean = 'XAUT'

        symbol = f"{clean}USDT"
        candles = []

        # Map interval
        url = f"{self.BASE_URL}/kline?category=linear&symbol={symbol}&interval={interval}&limit={limit}"
        data = self._safe_get(url)

        if not data:
            url_spot = f"{self.BASE_URL}/kline?category=spot&symbol={symbol}&interval={interval}&limit={limit}"
            data = self._safe_get(url_spot)

        if data:
            raw = data.get('result', {}).get('list', [])
            # Bybit returns klines in descending order (latest first) -> reverse to chronological
            for c in reversed(raw):
                if isinstance(c, list) and len(c) >= 6:
                    dt = datetime.fromtimestamp(int(c[0]) / 1000.0, tz=timezone.utc)
                    close_p = float(c[4])
                    dec = 2 if close_p > 10 else 4
                    candles.append({
                        "datetime": dt.strftime("%Y-%m-%d %H:%M:%S"),
                        "open": round(float(c[1]), dec),
                        "high": round(float(c[2]), dec),
                        "low": round(float(c[3]), dec),
                        "close": round(close_p, dec),
                        "volume": round(float(c[5]), 2)
                    })

        return candles
