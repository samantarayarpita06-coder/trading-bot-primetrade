"""
Input validation for trading bot CLI parameters.
All validators raise ValueError with a descriptive message on failure.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Optional

VALID_SIDES = {"BUY", "SELL"}
VALID_ORDER_TYPES = {"MARKET", "LIMIT", "STOP_MARKET"}


# ── Helpers ──────────────────────────────────────────────────────────────────

def _to_decimal(value: str, field: str) -> Decimal:
    """Convert a string to Decimal, raising ValueError on failure."""
    try:
        result = Decimal(str(value))
    except InvalidOperation:
        raise ValueError(f"'{field}' must be a valid number, got: {value!r}")
    if result <= 0:
        raise ValueError(f"'{field}' must be greater than zero, got: {result}")
    return result


# ── Public validators ────────────────────────────────────────────────────────

def validate_symbol(symbol: str) -> str:
    """Validate and normalise a trading symbol (e.g. BTCUSDT)."""
    if not symbol or not isinstance(symbol, str):
        raise ValueError("'symbol' must be a non-empty string.")
    normalised = symbol.strip().upper()
    if len(normalised) < 4:
        raise ValueError(f"'symbol' looks too short: {normalised!r}")
    return normalised


def validate_side(side: str) -> str:
    """Validate order side: BUY or SELL."""
    if not side or not isinstance(side, str):
        raise ValueError("'side' must be a non-empty string.")
    normalised = side.strip().upper()
    if normalised not in VALID_SIDES:
        raise ValueError(
            f"'side' must be one of {sorted(VALID_SIDES)}, got: {normalised!r}"
        )
    return normalised


def validate_order_type(order_type: str) -> str:
    """Validate order type: MARKET, LIMIT, or STOP_MARKET."""
    if not order_type or not isinstance(order_type, str):
        raise ValueError("'order_type' must be a non-empty string.")
    normalised = order_type.strip().upper()
    if normalised not in VALID_ORDER_TYPES:
        raise ValueError(
            f"'order_type' must be one of {sorted(VALID_ORDER_TYPES)}, got: {normalised!r}"
        )
    return normalised


def validate_quantity(quantity: str | float) -> Decimal:
    """Validate order quantity (must be > 0)."""
    return _to_decimal(quantity, "quantity")


def validate_price(price: Optional[str | float], order_type: str) -> Optional[Decimal]:
    """
    Validate price field.
    - Required for LIMIT and STOP_MARKET orders.
    - Must be > 0 when provided.
    """
    if order_type in ("LIMIT", "STOP_MARKET"):
        if price is None:
            raise ValueError(f"'price' is required for {order_type} orders.")
        return _to_decimal(price, "price")

    # MARKET order — price is ignored
    if price is not None:
        return _to_decimal(price, "price")  # accept but won't be sent
    return None


def validate_all(
    symbol: str,
    side: str,
    order_type: str,
    quantity: str | float,
    price: Optional[str | float] = None,
) -> dict:
    """
    Run all validators and return a clean params dict.

    Returns:
        {
            "symbol": str,
            "side": str,
            "order_type": str,
            "quantity": Decimal,
            "price": Decimal | None,
        }
    """
    sym = validate_symbol(symbol)
    sd = validate_side(side)
    ot = validate_order_type(order_type)
    qty = validate_quantity(quantity)
    prc = validate_price(price, ot)

    return {
        "symbol": sym,
        "side": sd,
        "order_type": ot,
        "quantity": qty,
        "price": prc,
    }
