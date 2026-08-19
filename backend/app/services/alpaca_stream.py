import json
import os
import asyncio
from collections.abc import AsyncIterator
from typing import Any

import websockets


class AlpacaStreamConfigError(RuntimeError):
    pass


SUPPORTED_ALPACA_FEEDS = {"iex", "sip", "delayed_sip", "test"}
ALPACA_AUTH_TIMEOUT_SECONDS = 10


def public_alpaca_stream_error(code: object | None) -> str:
    if code == 406:
        return "Live data connection limit reached. Close other live chart tabs and retry."
    if code in {401, 402, 403}:
        return "Live data provider authentication or subscription failed."
    return "Live data provider is unavailable. Try again later."


def _alpaca_key_id() -> str | None:
    return os.getenv("ALPACA_API_KEY_ID") or os.getenv("APCA_API_KEY_ID")


def _alpaca_secret_key() -> str | None:
    return os.getenv("ALPACA_API_SECRET_KEY") or os.getenv("APCA_API_SECRET_KEY")


def alpaca_feed() -> str:
    return (os.getenv("ALPACA_DATA_FEED", "iex").strip() or "iex").lower()


def alpaca_stream_url() -> str:
    override = os.getenv("ALPACA_STREAM_URL")
    if override:
        return override
    feed = alpaca_feed()
    if feed not in SUPPORTED_ALPACA_FEEDS:
        raise AlpacaStreamConfigError(f"Unsupported Alpaca data feed: {feed}")
    return f"wss://stream.data.alpaca.markets/v2/{feed}"


def _as_float(value: Any) -> float:
    return float(value)


def _as_int(value: Any) -> int:
    return int(value)


def parse_alpaca_bar(message: dict[str, Any]) -> dict[str, str | float | int] | None:
    if message.get("T") not in {"b", "u", "d"}:
        return None

    return {
        "type": "bar",
        "ticker": str(message["S"]).upper(),
        "timestamp": str(message["t"]),
        "open": _as_float(message["o"]),
        "high": _as_float(message["h"]),
        "low": _as_float(message["l"]),
        "close": _as_float(message["c"]),
        "volume": _as_int(message["v"]),
        "trade_count": _as_int(message.get("n", 0)),
        "vwap": _as_float(message.get("vw", message["c"])),
        "source": f"alpaca_{alpaca_feed()}",
    }


async def stream_alpaca_bars(ticker: str) -> AsyncIterator[dict[str, Any]]:
    key_id = _alpaca_key_id()
    secret_key = _alpaca_secret_key()
    if not key_id or not secret_key:
        raise AlpacaStreamConfigError("Set ALPACA_API_KEY_ID and ALPACA_API_SECRET_KEY to enable live candles.")

    symbol = ticker.upper()
    # Keep Alpaca credentials server-side; browsers only connect to the FastAPI WebSocket proxy.
    async with websockets.connect(alpaca_stream_url()) as alpaca:
        yield {"type": "status", "ticker": symbol, "message": f"Connected to Alpaca {alpaca_feed()} stream."}
        await alpaca.send(json.dumps({"action": "auth", "key": key_id, "secret": secret_key}))
        authenticated = False

        # Wait for Alpaca's auth acknowledgement before subscribing so the UI can surface auth/limit errors clearly.
        while not authenticated:
            try:
                raw_message = await asyncio.wait_for(alpaca.recv(), timeout=ALPACA_AUTH_TIMEOUT_SECONDS)
            except TimeoutError:
                yield {
                    "type": "error",
                    "ticker": symbol,
                    "message": "Alpaca did not confirm authentication before the timeout.",
                    "source": f"alpaca_{alpaca_feed()}",
                }
                return

            messages = json.loads(raw_message)
            if isinstance(messages, dict):
                messages = [messages]

            for message in messages:
                if message.get("T") == "error":
                    code = message.get("code")
                    yield {
                        "type": "error",
                        "ticker": symbol,
                        "message": public_alpaca_stream_error(code),
                        "code": code,
                        "source": f"alpaca_{alpaca_feed()}",
                    }
                    return
                if message.get("T") == "success" and message.get("msg") == "authenticated":
                    authenticated = True
                    yield {"type": "status", "ticker": symbol, "message": "Authenticated with Alpaca."}
                    break

        await alpaca.send(json.dumps({"action": "subscribe", "bars": [symbol]}))
        yield {"type": "status", "ticker": symbol, "message": f"Subscribed to {symbol} minute bars. Waiting for the next bar."}

        async for raw_message in alpaca:
            messages = json.loads(raw_message)
            if isinstance(messages, dict):
                messages = [messages]

            for message in messages:
                if message.get("T") == "error":
                    code = message.get("code")
                    yield {
                        "type": "error",
                        "ticker": symbol,
                        "message": public_alpaca_stream_error(code),
                        "code": code,
                        "source": f"alpaca_{alpaca_feed()}",
                    }
                    return

                bar = parse_alpaca_bar(message)
                if bar and bar["ticker"] == symbol:
                    # Alpaca minute bars may be sparse outside active US market trading.
                    yield bar
