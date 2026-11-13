"""Main Execution Entrypoint for Bybit Crypto Options Greeks & Candlesticks Actor."""

import asyncio
import logging
import math
import sys
from datetime import datetime, timezone
from typing import Dict, Any, List
from apify import Actor

from src.bybit_client import BybitClient
from src.greeks_engine import BybitGreeksEngine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("bybit-options-greeks-actor")


async def _build_proxy_urls(actor_input: Dict[str, Any]) -> List[str]:
    """Build non-US proxy URLs from Apify Proxy to bypass Bybit US CloudFront 403 blocks."""
    proxy_urls: List[str] = []
    seen = set()

    def _add(url: str) -> None:
        if url and url not in seen:
            seen.add(url)
            proxy_urls.append(url)

    proxy_settings = actor_input.get("proxyConfiguration")
    if isinstance(proxy_settings, dict) and proxy_settings:
        try:
            proxy_cfg = await Actor.create_proxy_configuration(actor_proxy_input=proxy_settings)
            if proxy_cfg:
                for _ in range(2):
                    u = await proxy_cfg.new_url()
                    if u:
                        _add(u)
        except Exception as e:
            logger.warning(f"Configured proxyConfiguration unavailable ({e}); trying fallback non-US proxy pools.")

    # Candidate non-US countries / groups in case input had no proxy or datacenter US IP was assigned
    fallback_specs = [
        {"country_code": "DE"},
        {"country_code": "FR"},
        {"country_code": "SG"},
        {"groups": ["RESIDENTIAL"], "country_code": "DE"},
    ]
    for spec in fallback_specs:
        try:
            cfg = await Actor.create_proxy_configuration(**spec)
            if cfg:
                u = await cfg.new_url()
                if u:
                    _add(u)
        except Exception:
            continue

    return proxy_urls


async def main() -> None:
    """Actor main routine."""
    async with Actor:
        actor_input = await Actor.get_input() or {}

        raw_currencies = actor_input.get("currencies", ["BTC", "ETH", "SOL"])
        if isinstance(raw_currencies, str):
            currencies_list = [c.strip().upper() for c in raw_currencies.split(",") if c.strip()]
        else:
            currencies_list = [str(c).strip().upper() for c in raw_currencies if str(c).strip()]

        if not currencies_list:
            currencies_list = ["BTC", "ETH", "SOL"]

        interval = str(actor_input.get("candlestickInterval", "D")).strip()
        limit = max(5, min(500, int(actor_input.get("candlestickLimit", 30))))
        max_expirations = max(1, min(20, int(actor_input.get("maxExpirationsPerCurrency", 4))))
        include_candles = bool(actor_input.get("includeCandlesticks", True))
        include_oi_volume = bool(actor_input.get("includeOiVolumeTable", True))
        include_full_greeks = bool(actor_input.get("includeFullGreeksTable", True))

        logger.info("Starting Bybit Crypto Options Greeks & Candlesticks Actor...")
        logger.info(f"Target Currencies: {currencies_list}, Interval: {interval}, Max Expirations: {max_expirations}")

        proxy_urls = await _build_proxy_urls(actor_input)
        if proxy_urls:
            logger.info(f"Configured {len(proxy_urls)} proxy candidate(s) for Bybit V5 requests.")
        else:
            logger.warning("No Apify Proxy available in environment; attempting direct Bybit V5 connection.")

        client = BybitClient(proxy_urls=proxy_urls)
        engine = BybitGreeksEngine(client)

        all_results: List[Dict[str, Any]] = []
        dataset_records: List[Dict[str, Any]] = []
        total_candles = 0

        for currency in currencies_list:
            logger.info(f"Fetching Bybit data for {currency}...")

            # 1. Klines Candlesticks from Bybit
            candles = []
            if include_candles:
                candles = client.get_klines(
                    currency=currency,
                    interval=interval,
                    limit=limit
                )
                total_candles += len(candles)
                logger.info(f"Retrieved {len(candles)} OHLCV candlesticks for {currency} from Bybit.")

            # 2. Options Chains & Greeks
            processed_data = engine.process_currency_options(
                currency=currency,
                max_expirations=max_expirations,
                include_oi_volume=include_oi_volume,
                include_full_greeks=include_full_greeks,
            )

            all_records = processed_data.pop("allRecords", [])
            dataset_records.extend(all_records)

            all_results.append({
                "currency": currency,
                "underlyingPriceUsd": processed_data["underlyingPriceUsd"],
                "candlesticksCount": len(candles),
                "candlesticks": candles,
                "expirationsCount": processed_data["expirationsCount"],
                "chains": processed_data["chains"]
            })

        # Push to Apify Default Dataset
        if dataset_records:
            sanitized_records = [
                {k: v for k, v in rec.items() if v is not None and not (isinstance(v, float) and not math.isfinite(v))}
                for rec in dataset_records
            ]
            logger.info(f"Pushing {len(sanitized_records)} strike options records to Apify dataset...")
            await Actor.push_data(sanitized_records)

        # Save comprehensive summary to Key-Value Store (OUTPUT)
        output_payload = {
            "status": "COMPLETED" if (dataset_records or total_candles > 0) else "FAILED",
            "title": "Bybit Crypto Options Greeks, Candlesticks & Open Interest Report",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "currenciesAnalyzed": len(all_results),
            "totalOptionStrikes": len(dataset_records),
            "totalCandlesticks": total_candles,
            "diagnostics": {
                "successfulRequests": client.successful_requests,
                "blocked403Count": client.blocked_403_count,
                "lastError": client.last_error,
            },
            "results": all_results
        }
        await Actor.set_value("OUTPUT", output_payload)

        if not dataset_records:
            if client.successful_requests == 0:
                err_msg = (
                    f"All Bybit V5 requests failed (403 blocks: {client.blocked_403_count}). "
                    f"Last error: {client.last_error or 'No response from Bybit API'}. "
                    "Apify cloud runs in US-East AWS which Bybit CloudFront blocks by default; "
                    "ensure a non-US proxy country (e.g. DE, FR, SG) or Residential Proxy is enabled."
                )
            else:
                err_msg = "No Bybit option strike records were extracted."
            logger.error(err_msg)
            await Actor.fail(status_message=err_msg)
            return

        logger.info(
            f"Actor completed successfully! Processed {len(all_results)} Bybit crypto assets "
            f"across {len(dataset_records)} total live option strike records."
        )


if __name__ == "__main__":
    asyncio.run(main())
