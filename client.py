"""
Binance Futures Testnet REST client.

Handles HMAC-SHA256 request signing, HTTP transport, and raw API responses.
All public methods return the parsed JSON response or raise BinanceAPIError.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import requests

from bot.logging_config import setup_logger

# ── Constants ────────────────────────────────────────────────────────────────

TESTNET_BASE_URL = "https://demo-fapi.binance.com"
RECV_WINDOW = 60000  # ms — how long the server accepts a signed request


# ── Custom exceptions ────────────────────────────────────────────────────────

class BinanceAPIError(Exception):
    """Raised when Binance returns a non-2xx status or an error payload."""

    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(f"Binance API error {code}: {message}")


class BinanceNetworkError(Exception):
    """Raised on connection / timeout failures."""


# ── Client ───────────────────────────────────────────────────────────────────

class BinanceFuturesClient:
    """
    Thin wrapper around the Binance USDT-M Futures REST API (testnet).

    Usage
    -----
    client = BinanceFuturesClient(api_key="...", api_secret="...")
    response = client.place_order(symbol="BTCUSDT", side="BUY", ...)
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        base_url: str = TESTNET_BASE_URL,
        timeout: int = 10,
    ):
        if not api_key or not api_secret:
            raise ValueError("Both api_key and api_secret must be non-empty strings.")

        self._api_key = api_key
        self._api_secret = api_secret
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._session = requests.Session()
        self._session.headers.update(
            {
                "X-MBX-APIKEY": self._api_key,
                "Content-Type": "application/x-www-form-urlencoded",
            }
        )
        self._logger = setup_logger("trading_bot.client")
        self._logger.info("BinanceFuturesClient initialised (base_url=%s)", self._base_url)

    # ── Private helpers ──────────────────────────────────────────────────────

    def _sign(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Append timestamp + signature to a params dict (in-place copy)."""
        params = dict(params)
        params["timestamp"] = int(time.time() * 1000)
        params["recvWindow"] = RECV_WINDOW
        query_string = urlencode(params)
        signature = hmac.new(
            self._api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        params["signature"] = signature
        return params

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        signed: bool = False,
    ) -> Any:
        """
        Execute an HTTP request and return the parsed JSON body.

        Raises BinanceAPIError or BinanceNetworkError on failure.
        """
        url = f"{self._base_url}{endpoint}"
        params = params or {}

        if signed:
            params = self._sign(params)

        self._logger.debug(
            "REQUEST  %s %s | params=%s", method.upper(), endpoint, params
        )

        try:
            response = self._session.request(
                method,
                url,
                params=params if method.upper() == "GET" else None,
                data=params if method.upper() != "GET" else None,
                timeout=self._timeout,
            )
        except requests.exceptions.ConnectionError as exc:
            self._logger.error("Network connection error: %s", exc)
            raise BinanceNetworkError(f"Connection failed: {exc}") from exc
        except requests.exceptions.Timeout as exc:
            self._logger.error("Request timed out: %s", exc)
            raise BinanceNetworkError(f"Request timed out after {self._timeout}s") from exc
        except requests.exceptions.RequestException as exc:
            self._logger.error("Unexpected request error: %s", exc)
            raise BinanceNetworkError(f"Unexpected error: {exc}") from exc

        self._logger.debug(
            "RESPONSE %s %s | status=%s | body=%s",
            method.upper(),
            endpoint,
            response.status_code,
            response.text[:500],
        )

        try:
            data = response.json()
        except ValueError:
            self._logger.error("Non-JSON response: %s", response.text[:200])
            raise BinanceAPIError(-1, f"Non-JSON response: {response.text[:200]}")

        # Binance error payloads always include a "code" key with a negative int
        if isinstance(data, dict) and data.get("code", 0) < 0:
            raise BinanceAPIError(data["code"], data.get("msg", "Unknown error"))

        if not response.ok:
            raise BinanceAPIError(
                response.status_code, f"HTTP {response.status_code}: {response.text[:200]}"
            )

        return data

    # ── Public API methods ───────────────────────────────────────────────────

    def get_server_time(self) -> Dict[str, Any]:
        """Ping /fapi/v1/time — useful for connectivity checks."""
        return self._request("GET", "/fapi/v1/time")

    def get_exchange_info(self) -> Dict[str, Any]:
        """Return exchange info (all symbols, filters, etc.)."""
        return self._request("GET", "/fapi/v1/exchangeInfo")

    def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: str,
        price: Optional[str] = None,
        stop_price: Optional[str] = None,
        time_in_force: str = "GTC",
        reduce_only: bool = False,
    ) -> Dict[str, Any]:
        """
        Place a new order on Binance USDT-M Futures (testnet).

        Parameters
        ----------
        symbol       : Trading pair, e.g. "BTCUSDT"
        side         : "BUY" or "SELL"
        order_type   : "MARKET", "LIMIT", or "STOP_MARKET"
        quantity     : Order size as string (e.g. "0.001")
        price        : Limit price (required for LIMIT orders)
        stop_price   : Trigger price (required for STOP_MARKET orders)
        time_in_force: "GTC" (default), "IOC", or "FOK"
        reduce_only  : If True, only reduce an existing position
        """
        params: Dict[str, Any] = {
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "quantity": quantity,
        }

        if order_type == "LIMIT":
            if price is None:
                raise ValueError("price is required for LIMIT orders.")
            params["price"] = price
            params["timeInForce"] = time_in_force

        elif order_type == "STOP_MARKET":
            if stop_price is None:
                raise ValueError("stop_price is required for STOP_MARKET orders.")
            params["stopPrice"] = stop_price

        if reduce_only:
            params["reduceOnly"] = "true"

        self._logger.info(
            "Placing %s %s order | symbol=%s qty=%s price=%s",
            side,
            order_type,
            symbol,
            quantity,
            price or stop_price or "N/A",
        )

        return self._request("POST", "/fapi/v1/order", params=params, signed=True)

    def get_order(self, symbol: str, order_id: int) -> Dict[str, Any]:
        """Query a single order by orderId."""
        return self._request(
            "GET",
            "/fapi/v1/order",
            params={"symbol": symbol, "orderId": order_id},
            signed=True,
        )

    def cancel_order(self, symbol: str, order_id: int) -> Dict[str, Any]:
        """Cancel an open order."""
        self._logger.info("Cancelling order %s on %s", order_id, symbol)
        return self._request(
            "DELETE",
            "/fapi/v1/order",
            params={"symbol": symbol, "orderId": order_id},
            signed=True,
        )

    def get_account(self) -> Dict[str, Any]:
        """Return account information (balances, positions, etc.)."""
        return self._request("GET", "/fapi/v2/account", signed=True)

    def get_position_risk(self, symbol: Optional[str] = None) -> Any:
        """Return position risk info, optionally filtered by symbol."""
        params = {}
        if symbol:
            params["symbol"] = symbol
        return self._request("GET", "/fapi/v2/positionRisk", params=params, signed=True)
