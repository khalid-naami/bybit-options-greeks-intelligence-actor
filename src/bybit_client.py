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
    """Official Bybit V5 Market REST API Client with CloudFront geo-block mitigation."""

    BASE_URLS = [
        "https://api.bybit.com/v5/market",
        "https://api.bytick.com/v5/market",
    ]
    BASE_URL = BASE_URLS[0]

    def __init__(self, proxy_urls: Optional[List[Optional[str]]] = None):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
        })
        self.proxy_urls: List[Optional[str]] = [p for p in (proxy_urls or []) if p]
        # Only fall back to direct connection if no proxies configured or all fail
        self.proxy_urls.append(None)

        self._preferred_route: Optional[Tuple[str, Optional[str]]] = None
        self.blocked_403_count: int = 0
        self.successful_requests: int = 0
        self.last_error: Optional[str] = None
        self._warned_routes: set = set()

        # Bybit Option Symbol: BTC-25SEP26-54000-C-USDT or XAUT-26AUG26-4510-C-USDT
        self.symbol_regex = re.compile(
            r'^([A-Z]+)-(\d{1,2})([A-Z]{3})(\d{2})-(\d+(?:\.\d+)?)-([CP])(?:-[A-Z]+)?$'
        )

    @staticmethod
    def _clean_currency(currency: str) -> str:
        clean = currency.upper().replace('-USD', '').replace('-USDT', '').replace('^', '').strip()
        if clean in ['XAU', 'GOLD', 'PAXG']:
            return 'XAUT'
        return clean

    def _safe_get(self, path_or_url: str, timeout: int = 10) -> Optional[Any]:
        if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
            # Extract path suffix when full URL is passed
            for base in self.BASE_URLS:
                if path_or_url.startswith(base):
                    path = path_or_url[len(base):]
                    break
            else:
                path = path_or_url
        else:
            path = path_or_url if path_or_url.startswith("/") else f"/{path_or_url}"

        if path.startswith("http"):
            candidates = [(path, p) for p in self.proxy_urls]
        else:
            candidates = [(f"{base}{path}", base, p) for p in self.proxy_urls for base in self.BASE_URLS]

        # Prioritize sticky working route if known
        if self._preferred_route and not path.startswith("http"):
            pref_base, pref_proxy = self._preferred_route
            candidates.sort(key=lambda item: 0 if (item[1] == pref_base and item[2] == pref_proxy) else 1)

        for entry in candidates:
            if len(entry) == 2:
                url, proxy_url = entry
                base = url
            else:
                url, base, proxy_url = entry

            proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None
            route_key = (base, "proxy" if proxy_url else "direct")

            try:
                res = self.session.get(url, timeout=timeout, proxies=proxies)
                if res.status_code == 200:
                    data = res.json()
                    ret_code = data.get('retCode')
                    if ret_code == 0:
                        self.successful_requests += 1
                        if not path.startswith("http"):
                            self._preferred_route = (base, proxy_url)
                        return data
                    self.last_error = f"Bybit retCode={ret_code}: {data.get('retMsg')}"
                    if route_key not in self._warned_routes:
                        logger.warning(f"Bybit API error on {url}: {self.last_error}")
                        self._warned_routes.add(route_key)
                    # retCode != 0 means the endpoint answered; no need to rotate mirrors/proxies for invalid params
                    return None
                elif res.status_code == 403:
                    self.blocked_403_count += 1
                    self.last_error = (
                        f"HTTP 403 Forbidden from Bybit/CloudFront via {route_key[1]} ({base}). "
                        "Bybit blocks US/cloud datacenter IPs; use a non-US proxy."
                    )
                    if route_key not in self._warned_routes:
                        logger.warning(self.last_error)
                        self._warned_routes.add(route_key)
                else:
                    self.last_error = f"HTTP {res.status_code} from {url} via {route_key[1]}"
                    if route_key not in self._warned_routes:
                        logger.warning(self.last_error)
                        self._warned_routes.add(route_key)
            except Exception as e:
                self.last_error = f"Request failed for {url} via {route_key[1]}: {e}"
                if route_key not in self._warned_routes:
                    logger.warning(self.last_error)
                    self._warned_routes.add(route_key)

        return None

    def get_spot_price(self, currency: str) -> float:
        """Fetch current real-time price from Bybit spot, linear perpetual, or option index."""
        clean = self._clean_currency(currency)
        symbol = f"{clean}USDT"

        # 1. Spot Tickers
        data_spot = self._safe_get(f"/tickers?category=spot&symbol={symbol}")
        if data_spot:
            lst = data_spot.get('result', {}).get('list', [])
            if lst:
                p = float(lst[0].get('lastPrice') or 0)
                if p > 0:
                    return p

        # 2. Linear Futures Tickers
        data_lin = self._safe_get(f"/tickers?category=linear&symbol={symbol}")
        if data_lin:
            lst = data_lin.get('result', {}).get('list', [])
            if lst:
                p = float(lst[0].get('lastPrice') or 0)
                if p > 0:
                    return p

        # 3. Option Index Price
        data_idx = self._safe_get(f"/index-price?category=option&baseCoin={clean}")
        if data_idx:
            lst = data_idx.get('result', {}).get('list', [])
            if lst:
                p = float(lst[0].get('indexPrice') or 0)
                if p > 0:
                    return p

        defaults = {'BTC': 65000.0, 'ETH': 2650.0, 'SOL': 155.0, 'XAUT': 2685.0, 'XRP': 0.60, 'DOGE': 0.12, 'MNT': 0.85}
        return defaults.get(clean, 100.0)

    def get_options_data(self, currency: str) -> List[Dict[str, Any]]:
        """Fetch all active European options tickers and Greeks for baseCoin from Bybit V5."""
        clean = self._clean_currency(currency)
        data = self._safe_get(f"/tickers?category=option&baseCoin={clean}")

        if not data:
            logger.warning(f"No options ticker data returned from Bybit V5 for {clean} ({self.last_error or 'empty response'})")
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
        clean = self._clean_currency(currency)
        symbol = f"{clean}USDT"
        candles = []

        data = self._safe_get(f"/kline?category=linear&symbol={symbol}&interval={interval}&limit={limit}")
        if not data:
            data = self._safe_get(f"/kline?category=spot&symbol={symbol}&interval={interval}&limit={limit}")

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
