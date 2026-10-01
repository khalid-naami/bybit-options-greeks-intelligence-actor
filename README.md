# Bybit Crypto Options Greeks, Candlesticks & Volume Intelligence Actor

Institutional-grade quantitative crypto options data engine powered by **100% direct official Bybit V5 Market API (`api.bybit.com/v5`)**. Delivers **Live Bybit Klines OHLCV Candlestick Price Action**, **Strike-by-Strike Primary & Higher-Order Greeks Tables**, and **Open Interest & 24h Volume Distributions** across **BTC, ETH, SOL, XAUT (Tether Gold), XRP, DOGE, and MNT**.

---

## ⚡ Direct Official Bybit V5 Architecture

- **Zero Third-Party Scraping / Zero yfinance**: Connects directly to official Bybit endpoints (`/v5/market/tickers?category=option`, `/v5/market/kline`, and `/v5/market/index-price`).
- **No API Key Required**: Fully utilizes unauthenticated public REST endpoints.
- **European Cash-Settled Model**: Standardized USD valuation and native Bybit Mark IV calibration.

---

## 🚀 Supported Crypto Assets

| Asset | Base Coin | Contract Settled | Underlying Price Feed |
|---|---|---|---|
| **Bitcoin** | `BTC` | Cash-Settled (USDT) | `BTCUSDT` Spot / Index |
| **Ethereum** | `ETH` | Cash-Settled (USDT) | `ETHUSDT` Spot / Index |
| **Solana** | `SOL` | Cash-Settled (USDT) | `SOLUSDT` Spot / Index |
| **Tether Gold** | `XAUT` | Cash-Settled (USDT) | `XAUTUSDT` Spot / Index |
| **Ripple** | `XRP` | Cash-Settled (USDT) | `XRPUSDT` Spot / Index |
| **Dogecoin** | `DOGE` | Cash-Settled (USDT) | `DOGEUSDT` Spot / Index |
| **Mantle** | `MNT` | Cash-Settled (USDT) | `MNTUSDT` Spot / Index |

---

## 📊 Key Data Tables & Fields

### 1. Strike-by-Strike Greeks Dataset
- **Primary Greeks:**
  - `callDelta`, `putDelta`: Direct directional delta sensitivity.
  - `gamma`: Rate of change of Delta per \$1 underlying move.
  - `vega`: Option price sensitivity to 1% shift in Mark IV.
  - `callTheta`, `putTheta`: Daily time decay value.
- **Higher-Order Quantitative Greeks:**
  - `vanna`: Cross-derivative $\frac{\partial \text{Delta}}{\partial \text{IV}}$.
  - `charm`: Delta decay over time $\frac{\partial \text{Delta}}{\partial T}$.
  - `speed`: Third-order derivative $\frac{\partial \text{Gamma}}{\partial S}$.
  - `vomma`: Volatility convexity $\frac{\partial \text{Vega}}{\partial \text{IV}}$.
  - `color`: Gamma decay over time $\frac{\partial \text{Gamma}}{\partial T}$.
- **Breakevens:** Expiration breakevens ($K + \text{Call Price}$ and $K - \text{Put Price}$).

### 2. Open Interest & 24h Volume Distribution
- `callOpenInterest`, `putOpenInterest`, `netOpenInterest`
- `callVolume24h`, `putVolume24h`, `netVolume24h`
- Total Open Interest, Total Volume, and `Put/Call Ratio` ($PCR_{\text{OI}}$ & $PCR_{\text{Vol}}$).

### 3. Bybit Klines OHLCV Candlestick Price History
- Official Bybit spot/linear perpetual candlestick series (`open`, `high`, `low`, `close`, `volume`).

---

## 📥 Input Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `currencies` | `Array` | `["BTC", "ETH", "SOL"]` | List of cryptocurrency keys to fetch from Bybit Options. |
| `candlestickInterval` | `String` | `"D"` | Klines resolution interval (`5`, `15`, `60`, `240`, `D`). |
| `candlestickLimit` | `Integer` | `30` | Number of historical OHLCV candlestick bars. |
| `maxExpirationsPerCurrency` | `Integer` | `4` | Maximum expiration cycles to process per currency. |
| `includeCandlesticks` | `Boolean` | `true` | Include OHLCV series. |
| `includeOiVolumeTable` | `Boolean` | `true` | Include Open Interest and Volume columns. |
| `includeFullGreeksTable` | `Boolean` | `true` | Include primary & higher-order Greeks. |

---

## 📤 Output Structure

### 1. Default Dataset (Bybit Strike Options Table)
```json
{
  "currency": "BTC",
  "underlyingPriceUsd": 65420.50,
  "expirationDate": "2026-10-30",
  "daysToExpiration": 30,
  "strike": 66000.00,
  "callMarkPriceUsd": 3250.80,
  "putMarkPriceUsd": 3820.10,
  "callMarkIvPct": 54.25,
  "putMarkIvPct": 55.10,
  "callDelta": 0.4852,
  "putDelta": -0.5148,
  "gamma": 0.0000185,
  "vega": 98.42,
  "callTheta": -54.20,
  "putTheta": -51.85,
  "vanna": 0.000425,
  "charmCall": -0.000120,
  "speed": -0.00000001,
  "vomma": 0.1850,
  "color": -0.00000005,
  "callOpenInterest": 1845.2,
  "putOpenInterest": 1210.5,
  "netOpenInterest": 634.7,
  "callVolume24h": 412.0,
  "putVolume24h": 285.5,
  "netVolume24h": 126.5,
  "callBreakevenUsd": 69250.80,
  "putBreakevenUsd": 62179.90
}
```

### 2. Key-Value Store (`OUTPUT`)
Comprehensive JSON report with currency candlestick arrays and expiration totals summary.
