"""
Order placement logic — sits between the CLI and the raw Binance client.

Responsible for:
  - Calling validators before touching the API
  - Formatting the request summary for user display
  - Parsing and pretty-printing the API response
  - Logging the full round-trip
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, Optional

from bot.client import BinanceFuturesClient, BinanceAPIError, BinanceNetworkError
from bot.logging_config import setup_logger
from bot.validators import validate_all


logger = setup_logger("trading_bot.orders")


# ── Result dataclass (plain dict for simplicity) ─────────────────────────────

def _build_result(success: bool, summary: str, data: Optional[Dict] = None, error: str = "") -> Dict:
    return {"success": success, "summary": summary, "data": data or {}, "error": error}


# ── Display helpers ───────────────────────────────────────────────────────────

def format_order_request(params: Dict[str, Any]) -> str:
    """Return a human-readable order request summary."""
    lines = [
        "┌─────────────────────────────────────────┐",
        "│           ORDER REQUEST SUMMARY          │",
        "├─────────────────────────────────────────┤",
        f"│  Symbol     : {params['symbol']:<26}│",
        f"│  Side       : {params['side']:<26}│",
        f"│  Type       : {params['order_type']:<26}│",
        f"│  Quantity   : {str(params['quantity']):<26}│",
    ]
    if params.get("price"):
        lines.append(f"│  Price      : {str(params['price']):<26}│")
    lines.append("└─────────────────────────────────────────┘")
    return "\n".join(lines)


def format_order_response(response: Dict[str, Any]) -> str:
    """Return a human-readable order response summary."""
    order_id   = response.get("orderId", "N/A")
    status     = response.get("status", "N/A")
    exec_qty   = response.get("executedQty", "0")
    avg_price  = response.get("avgPrice", "0")
    orig_qty   = response.get("origQty", "N/A")
    symbol     = response.get("symbol", "N/A")
    side       = response.get("side", "N/A")
    order_type = response.get("type", "N/A")
    client_id  = response.get("clientOrderId", "N/A")
    update_time = response.get("updateTime", "N/A")

    lines = [
        "┌─────────────────────────────────────────┐",
        "│          ORDER RESPONSE DETAILS          │",
        "├─────────────────────────────────────────┤",
        f"│  Order ID   : {str(order_id):<26}│",
        f"│  Client ID  : {str(client_id):<26}│",
        f"│  Symbol     : {symbol:<26}│",
        f"│  Side       : {side:<26}│",
        f"│  Type       : {order_type:<26}│",
        f"│  Status     : {status:<26}│",
        f"│  Orig Qty   : {str(orig_qty):<26}│",
        f"│  Exec Qty   : {str(exec_qty):<26}│",
        f"│  Avg Price  : {str(avg_price):<26}│",
        f"│  Update Time: {str(update_time):<26}│",
        "└─────────────────────────────────────────┘",
    ]
    return "\n".join(lines)


# ── Core order function ───────────────────────────────────────────────────────

def place_order(
    client: BinanceFuturesClient,
    symbol: str,
    side: str,
    order_type: str,
    quantity: str | float,
    price: Optional[str | float] = None,
) -> Dict[str, Any]:
    """
    Validate inputs, place an order via the client, and return a result dict.

    Always returns a dict with keys: success, summary, data, error.
    Never raises — all exceptions are caught and recorded.
    """
    # ── Step 1: Validate ──────────────────────────────────────────────────────
    try:
        params = validate_all(
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
        )
    except ValueError as exc:
        logger.error("Validation failed: %s", exc)
        return _build_result(False, "", error=f"Validation error: {exc}")

    request_summary = format_order_request(params)
    logger.info(
        "Validated order: %s %s %s qty=%s price=%s",
        params["side"],
        params["order_type"],
        params["symbol"],
        params["quantity"],
        params.get("price", "N/A"),
    )

    # ── Step 2: Place via API ─────────────────────────────────────────────────
    try:
        response = client.place_order(
            symbol=params["symbol"],
            side=params["side"],
            order_type=params["order_type"],
            quantity=str(params["quantity"]),
            price=str(params["price"]) if params.get("price") else None,
        )
    except BinanceAPIError as exc:
        logger.error("API error placing order: code=%s msg=%s", exc.code, exc.message)
        return _build_result(False, request_summary, error=f"API error {exc.code}: {exc.message}")
    except BinanceNetworkError as exc:
        logger.error("Network error placing order: %s", exc)
        return _build_result(False, request_summary, error=f"Network error: {exc}")
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error placing order: %s", exc)
        return _build_result(False, request_summary, error=f"Unexpected error: {exc}")

    logger.info(
        "Order placed successfully | orderId=%s status=%s execQty=%s",
        response.get("orderId"),
        response.get("status"),
        response.get("executedQty"),
    )
    return _build_result(True, request_summary, data=response)


# ── Convenience wrappers ──────────────────────────────────────────────────────

def place_market_order(
    client: BinanceFuturesClient,
    symbol: str,
    side: str,
    quantity: str | float,
) -> Dict[str, Any]:
    """Shorthand for a MARKET order."""
    return place_order(client, symbol, side, "MARKET", quantity)


def place_limit_order(
    client: BinanceFuturesClient,
    symbol: str,
    side: str,
    quantity: str | float,
    price: str | float,
) -> Dict[str, Any]:
    """Shorthand for a LIMIT order."""
    return place_order(client, symbol, side, "LIMIT", quantity, price)


def place_stop_market_order(
    client: BinanceFuturesClient,
    symbol: str,
    side: str,
    quantity: str | float,
    stop_price: str | float,
) -> Dict[str, Any]:
    """
    Shorthand for a STOP_MARKET order (bonus order type).
    stop_price is passed as the price argument; client maps it to stopPrice.
    """
    # For STOP_MARKET we need special handling in client — pass via price for validation,
    # then override in client call
    try:
        params = validate_all(
            symbol=symbol,
            side=side,
            order_type="STOP_MARKET",
            quantity=quantity,
            price=stop_price,
        )
    except ValueError as exc:
        logger.error("Validation failed: %s", exc)
        return _build_result(False, "", error=f"Validation error: {exc}")

    request_summary = format_order_request(
        {**params, "order_type": "STOP_MARKET", "price": stop_price}
    )

    try:
        response = client.place_order(
            symbol=params["symbol"],
            side=params["side"],
            order_type="STOP_MARKET",
            quantity=str(params["quantity"]),
            stop_price=str(params["price"]),
        )
    except BinanceAPIError as exc:
        logger.error("API error placing STOP_MARKET: code=%s msg=%s", exc.code, exc.message)
        return _build_result(False, request_summary, error=f"API error {exc.code}: {exc.message}")
    except BinanceNetworkError as exc:
        logger.error("Network error: %s", exc)
        return _build_result(False, request_summary, error=f"Network error: {exc}")
    except Exception as exc:
        logger.exception("Unexpected error: %s", exc)
        return _build_result(False, request_summary, error=f"Unexpected error: {exc}")

    logger.info(
        "STOP_MARKET order placed | orderId=%s status=%s",
        response.get("orderId"),
        response.get("status"),
    )
    return _build_result(True, request_summary, data=response)
