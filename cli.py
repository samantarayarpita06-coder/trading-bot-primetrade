#!/usr/bin/env python3
"""
cli.py — Command-line interface for the Binance Futures Testnet trading bot.

Usage examples
--------------
# Market BUY
python cli.py --symbol BTCUSDT --side BUY --type MARKET --quantity 0.001

# Limit SELL
python cli.py --symbol BTCUSDT --side SELL --type LIMIT --quantity 0.001 --price 70000

# Stop-Market BUY (bonus order type)
python cli.py --symbol BTCUSDT --side BUY --type STOP_MARKET --quantity 0.001 --price 95000

# Override credentials inline (not recommended for production)
python cli.py --api-key YOUR_KEY --api-secret YOUR_SECRET --symbol ETHUSDT ...

# Interactive menu mode
python cli.py --interactive
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Optional

from bot.client import BinanceFuturesClient, BinanceAPIError, BinanceNetworkError
from bot.logging_config import setup_logger
from bot.orders import (
    format_order_response,
    place_limit_order,
    place_market_order,
    place_stop_market_order,
    place_order,
)

logger = setup_logger("trading_bot.cli")

# ── ANSI colours (graceful fallback on Windows without colorama) ──────────────
try:
    import colorama
    colorama.init(autoreset=True)
    GREEN  = colorama.Fore.GREEN
    RED    = colorama.Fore.RED
    YELLOW = colorama.Fore.YELLOW
    CYAN   = colorama.Fore.CYAN
    RESET  = colorama.Style.RESET_ALL
except ImportError:
    GREEN = RED = YELLOW = CYAN = RESET = ""


# ── Banner ────────────────────────────────────────────────────────────────────

BANNER = f"""{CYAN}
╔══════════════════════════════════════════════╗
║   Binance Futures Testnet Trading Bot        ║
║   USDT-M Futures | Primetrade.ai Task        ║
╚══════════════════════════════════════════════╝
{RESET}"""


# ── Credential helpers ────────────────────────────────────────────────────────

def get_credentials(api_key: Optional[str], api_secret: Optional[str]) -> tuple[str, str]:
    """
    Resolve API credentials with the following priority:
      1. CLI flags (--api-key / --api-secret)
      2. Environment variables BINANCE_API_KEY / BINANCE_API_SECRET
      3. .env file in the current directory (minimal manual parse)
    """
    key    = api_key    or os.environ.get("BINANCE_API_KEY", "")
    secret = api_secret or os.environ.get("BINANCE_API_SECRET", "")

    # Minimal .env support (no python-dotenv dependency required)
    if not key or not secret:
        env_path = os.path.join(os.path.dirname(__file__), ".env")
        if os.path.isfile(env_path):
            with open(env_path, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line.startswith("#") or "=" not in line:
                        continue
                    k, _, v = line.partition("=")
                    k, v = k.strip(), v.strip().strip('"').strip("'")
                    if k == "BINANCE_API_KEY" and not key:
                        key = v
                    elif k == "BINANCE_API_SECRET" and not secret:
                        secret = v

    if not key or not secret:
        print(
            f"{RED}✗ API credentials not found.\n"
            "  Set BINANCE_API_KEY and BINANCE_API_SECRET as environment variables,\n"
            "  add them to a .env file next to cli.py, or pass --api-key / --api-secret.{RESET}"
        )
        sys.exit(1)

    return key, secret


# ── Output helpers ────────────────────────────────────────────────────────────

def print_result(result: dict) -> None:
    """Print request summary, response, and success/failure message."""
    if result.get("summary"):
        print(result["summary"])

    if result["success"]:
        print(format_order_response(result["data"]))
        print(f"\n{GREEN}✓ Order placed successfully!{RESET}\n")
        logger.info("Order completed successfully — orderId=%s", result["data"].get("orderId"))
    else:
        print(f"\n{RED}✗ Order failed: {result['error']}{RESET}\n")
        logger.error("Order failed: %s", result["error"])


# ── Interactive mode ──────────────────────────────────────────────────────────

def interactive_mode(client: BinanceFuturesClient) -> None:
    """Enhanced interactive CLI with menus and guided prompts."""
    print(BANNER)

    while True:
        print(f"{CYAN}━━━  Main Menu  ━━━{RESET}")
        print("  1. Place a new order")
        print("  2. Check account balance")
        print("  3. Exit")
        choice = input(f"\n{YELLOW}Select option [1-3]: {RESET}").strip()

        if choice == "3":
            print(f"{GREEN}Goodbye!{RESET}")
            break

        elif choice == "2":
            print(f"\n{CYAN}Fetching account info…{RESET}")
            try:
                account = client.get_account()
                assets = [a for a in account.get("assets", []) if float(a.get("walletBalance", 0)) > 0]
                if assets:
                    print(f"\n{'Asset':<10} {'Wallet Balance':<20} {'Available Balance'}")
                    print("─" * 50)
                    for a in assets:
                        print(f"{a['asset']:<10} {a['walletBalance']:<20} {a['availableBalance']}")
                else:
                    print("No funded assets found.")
                print()
            except (BinanceAPIError, BinanceNetworkError) as exc:
                print(f"{RED}Error: {exc}{RESET}")

        elif choice == "1":
            print(f"\n{CYAN}━━━  New Order  ━━━{RESET}")

            symbol = input(f"  Symbol (e.g. BTCUSDT): {RESET}").strip().upper()

            print(f"\n  Side options: {YELLOW}BUY{RESET} / {YELLOW}SELL{RESET}")
            side = input("  Side: ").strip().upper()

            print(f"\n  Order types: {YELLOW}1{RESET} MARKET  {YELLOW}2{RESET} LIMIT  {YELLOW}3{RESET} STOP_MARKET")
            type_map = {"1": "MARKET", "2": "LIMIT", "3": "STOP_MARKET"}
            type_input = input("  Select type [1-3]: ").strip()
            order_type = type_map.get(type_input, type_input.upper())

            quantity = input("  Quantity: ").strip()

            price = None
            if order_type in ("LIMIT", "STOP_MARKET"):
                label = "Limit price" if order_type == "LIMIT" else "Stop trigger price"
                price = input(f"  {label}: ").strip()

            print()
            result = place_order(client, symbol, side, order_type, quantity, price)
            print_result(result)

        else:
            print(f"{RED}Invalid option. Please enter 1, 2, or 3.{RESET}\n")


# ── Argument parser ───────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="trading_bot",
        description="Binance Futures Testnet Trading Bot — place MARKET, LIMIT, and STOP_MARKET orders.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cli.py --symbol BTCUSDT --side BUY  --type MARKET     --quantity 0.001
  python cli.py --symbol BTCUSDT --side SELL --type LIMIT       --quantity 0.001 --price 70000
  python cli.py --symbol BTCUSDT --side BUY  --type STOP_MARKET --quantity 0.001 --price 95000
  python cli.py --interactive
        """,
    )

    # ── Credentials (optional — fall back to env vars / .env) ────────────────
    creds = parser.add_argument_group("credentials (optional — prefer env vars)")
    creds.add_argument("--api-key",    metavar="KEY",    help="Binance Testnet API key")
    creds.add_argument("--api-secret", metavar="SECRET", help="Binance Testnet API secret")

    # ── Order parameters ──────────────────────────────────────────────────────
    order = parser.add_argument_group("order parameters")
    order.add_argument(
        "--symbol", "-s",
        metavar="SYMBOL",
        help="Trading pair, e.g. BTCUSDT",
    )
    order.add_argument(
        "--side",
        metavar="SIDE",
        choices=["BUY", "SELL"],
        help="Order side: BUY or SELL",
    )
    order.add_argument(
        "--type", "-t",
        dest="order_type",
        metavar="TYPE",
        choices=["MARKET", "LIMIT", "STOP_MARKET"],
        help="Order type: MARKET, LIMIT, or STOP_MARKET",
    )
    order.add_argument(
        "--quantity", "-q",
        metavar="QTY",
        help="Order quantity (e.g. 0.001)",
    )
    order.add_argument(
        "--price", "-p",
        metavar="PRICE",
        default=None,
        help="Limit / stop price — required for LIMIT and STOP_MARKET orders",
    )

    # ── Interactive mode ──────────────────────────────────────────────────────
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Launch the interactive menu-driven interface",
    )

    return parser


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    print(BANNER)

    # Resolve credentials
    api_key, api_secret = get_credentials(args.api_key, args.api_secret)

    # Build client
    try:
        client = BinanceFuturesClient(api_key=api_key, api_secret=api_secret)
    except ValueError as exc:
        print(f"{RED}✗ Client initialisation error: {exc}{RESET}")
        sys.exit(1)

    # Verify connectivity
    try:
        server_time = client.get_server_time()
        logger.info("Connected to Binance Testnet — server time: %s", server_time)
        print(f"{GREEN}✓ Connected to Binance Futures Testnet{RESET}\n")
    except (BinanceAPIError, BinanceNetworkError) as exc:
        print(f"{RED}✗ Cannot reach Binance Testnet: {exc}{RESET}")
        logger.error("Connectivity check failed: %s", exc)
        sys.exit(1)

    # ── Interactive mode ──────────────────────────────────────────────────────
    if args.interactive:
        interactive_mode(client)
        return

    # ── Non-interactive: validate required args ───────────────────────────────
    missing = [f"--{f}" for f, v in [
        ("symbol", args.symbol),
        ("side", args.side),
        ("type", args.order_type),
        ("quantity", args.quantity),
    ] if not v]

    if missing:
        print(
            f"{RED}✗ The following arguments are required for non-interactive mode: "
            f"{', '.join(missing)}\n\n"
            f"Tip: run with --interactive for a guided experience.{RESET}"
        )
        parser.print_usage()
        sys.exit(1)

    # ── Place the order ───────────────────────────────────────────────────────
    result = place_order(
        client=client,
        symbol=args.symbol,
        side=args.side,
        order_type=args.order_type,
        quantity=args.quantity,
        price=args.price,
    )
    print_result(result)
    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
