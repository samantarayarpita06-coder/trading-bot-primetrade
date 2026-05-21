# Binance Futures Testnet Trading Bot

A clean, well-structured Python CLI application to place orders on **Binance USDT-M Futures Testnet**.

---

## Project Structure

```
trading_bot/
├── bot/
│   ├── __init__.py          # Package init
│   ├── client.py            # Binance REST client (signing, HTTP, error handling)
│   ├── orders.py            # Order placement logic + display formatting
│   ├── validators.py        # Input validation (symbol, side, type, qty, price)
│   └── logging_config.py   # Structured file + console logging setup
├── cli.py                   # CLI entry point (argparse + interactive mode)
├── logs/                    # Auto-created; log files written here
│   └── trading_bot_YYYYMMDD.log
├── .env.example             # Template for API credentials
├── requirements.txt
└── README.md
```

---

## Setup

### 1. Get Testnet API Credentials

1. Visit [https://testnet.binancefuture.com](https://testnet.binancefuture.com)
2. Log in with GitHub
3. Go to **API Key** tab → generate a new key pair
4. Copy your **API Key** and **Secret Key**

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

Requires Python 3.9+. No additional setup needed.

### 3. Set API Credentials

**Option A — `.env` file (recommended)**

```bash
cp .env.example .env
# Edit .env and paste your keys
```

`.env` file format:
```
BINANCE_API_KEY=your_api_key_here
BINANCE_API_SECRET=your_api_secret_here
```

**Option B — Environment variables**

```bash
export BINANCE_API_KEY=your_api_key_here
export BINANCE_API_SECRET=your_api_secret_here
```

**Option C — CLI flags** (not recommended for production)

```bash
python cli.py --api-key YOUR_KEY --api-secret YOUR_SECRET ...
```

---

## How to Run

### Non-Interactive Mode (one-shot commands)

```bash
# MARKET BUY — buy 0.001 BTC at current market price
python cli.py --symbol BTCUSDT --side BUY --type MARKET --quantity 0.001

# LIMIT SELL — place a sell order at $108,000
python cli.py --symbol BTCUSDT --side SELL --type LIMIT --quantity 0.001 --price 108000

# STOP_MARKET BUY — trigger a buy when price hits $95,000 (bonus order type)
python cli.py --symbol BTCUSDT --side BUY --type STOP_MARKET --quantity 0.001 --price 95000

# ETH example
python cli.py --symbol ETHUSDT --side BUY --type MARKET --quantity 0.01
```

### Interactive / Menu Mode

```bash
python cli.py --interactive
```

Presents a guided menu for placing orders and checking account balance.

### Help

```bash
python cli.py --help
```

---

## Sample Output

### MARKET BUY
```
╔══════════════════════════════════════════════╗
║   Binance Futures Testnet Trading Bot        ║
║   USDT-M Futures | Primetrade.ai Task        ║
╚══════════════════════════════════════════════╝

✓ Connected to Binance Futures Testnet

┌─────────────────────────────────────────┐
│           ORDER REQUEST SUMMARY          │
├─────────────────────────────────────────┤
│  Symbol     : BTCUSDT                   │
│  Side       : BUY                       │
│  Type       : MARKET                    │
│  Quantity   : 0.001                     │
└─────────────────────────────────────────┘
┌─────────────────────────────────────────┐
│          ORDER RESPONSE DETAILS          │
├─────────────────────────────────────────┤
│  Order ID   : 4811729381                │
│  Symbol     : BTCUSDT                   │
│  Side       : BUY                       │
│  Type       : MARKET                    │
│  Status     : FILLED                    │
│  Orig Qty   : 0.001                     │
│  Exec Qty   : 0.001                     │
│  Avg Price  : 104823.50                 │
└─────────────────────────────────────────┘

✓ Order placed successfully!
```

---

## Order Types Supported

| Type | Description | `--price` required? |
|------|-------------|---------------------|
| `MARKET` | Executes immediately at best available price | No |
| `LIMIT` | Rests in the book at your specified price | Yes |
| `STOP_MARKET` | Triggers a market order when price hits stop level | Yes (stop price) |

---

## CLI Arguments

| Argument | Description | Required |
|----------|-------------|----------|
| `--symbol` / `-s` | Trading pair (e.g. `BTCUSDT`) | Yes |
| `--side` | `BUY` or `SELL` | Yes |
| `--type` / `-t` | `MARKET`, `LIMIT`, or `STOP_MARKET` | Yes |
| `--quantity` / `-q` | Order size (e.g. `0.001`) | Yes |
| `--price` / `-p` | Limit or stop price | For LIMIT / STOP_MARKET |
| `--api-key` | Binance API key (prefers env var) | No |
| `--api-secret` | Binance API secret (prefers env var) | No |
| `--interactive` / `-i` | Launch interactive menu | No |

---

## Logging

Logs are written to `logs/trading_bot_YYYYMMDD.log`. Each file contains:

- **DEBUG** — full API request params and raw response bodies
- **INFO** — order summaries, connectivity checks, results
- **ERROR** — validation failures, API errors, network failures

Console output shows INFO and above only. The log directory is created automatically.

---

## Error Handling

| Scenario | Behaviour |
|----------|-----------|
| Missing required fields | Validation error before any API call |
| Invalid symbol / quantity / price | Clear message, no API call made |
| Binance API error (e.g. `-2019 Margin insufficient`) | Error code + message displayed and logged |
| Network timeout / connection failure | Friendly message + logged stack trace |
| Missing credentials | Startup exit with clear instructions |

---

## Assumptions

1. **Testnet only** — the base URL is hardcoded to `https://testnet.binancefuture.com`. To use mainnet, change `TESTNET_BASE_URL` in `bot/client.py`.
2. **Position mode** — assumes the testnet account is in **One-Way mode** (default). Hedge mode requires adding `positionSide` to requests.
3. **Quantity precision** — the testnet is forgiving; production use requires respecting the symbol's `LOT_SIZE` filter.
4. **No position auto-close** — `reduceOnly=False` by default; orders open new positions or add to them.
5. **`colorama` optional** — if not installed, ANSI colour codes are suppressed gracefully.

---

## Dependencies

```
requests>=2.31.0    # HTTP client
colorama>=0.4.6     # Cross-platform ANSI colour output (optional)
```

No `python-binance` library used — all API interaction is via direct REST calls for full transparency and control.
