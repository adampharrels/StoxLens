import os
import re

from fastapi import APIRouter, WebSocket
from starlette.websockets import WebSocketDisconnect

from app.services.alpaca_stream import AlpacaStreamConfigError, stream_alpaca_bars

router = APIRouter()

TICKER_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9.\-]{0,15}$")
DEFAULT_ALLOWED_ORIGINS = {
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
}
_active_streams_by_client: dict[str, int] = {}


def _allowed_origins() -> set[str]:
    configured = os.getenv("CORS_ORIGINS")
    if not configured:
        return DEFAULT_ALLOWED_ORIGINS
    return {origin.strip() for origin in configured.split(",") if origin.strip()}


def _live_connection_limit() -> int:
    try:
        return int(os.getenv("LIVE_CANDLE_CONNECTION_LIMIT", "2"))
    except ValueError:
        return 2


def _client_key(websocket: WebSocket) -> str:
    return websocket.client.host if websocket.client else "unknown"


@router.websocket("/candles")
async def websocket_candles(websocket: WebSocket) -> None:
    origin = websocket.headers.get("origin")
    if origin and origin not in _allowed_origins():
        await websocket.close(code=1008)
        return

    await websocket.accept()
    ticker = (websocket.query_params.get("ticker") or "").strip().upper()
    if not ticker or not TICKER_PATTERN.fullmatch(ticker):
        await websocket.send_json({"type": "error", "message": "Valid ticker query parameter is required"})
        await websocket.close(code=1008)
        return

    client_key = _client_key(websocket)
    active_count = _active_streams_by_client.get(client_key, 0)
    if active_count >= _live_connection_limit():
        await websocket.send_json(
            {
                "type": "error",
                "ticker": ticker,
                "message": "Live candle connection limit reached. Close another live chart tab and retry.",
            }
        )
        await websocket.close(code=1008)
        return

    _active_streams_by_client[client_key] = active_count + 1
    try:
        await websocket.send_json({"type": "status", "ticker": ticker, "message": "Connecting to Alpaca live bars."})
        async for candle in stream_alpaca_bars(ticker):
            await websocket.send_json(candle)
    except AlpacaStreamConfigError as exc:
        await websocket.send_json({"type": "error", "ticker": ticker, "message": str(exc)})
        await websocket.close(code=1008)
    except WebSocketDisconnect:
        return
    finally:
        remaining = _active_streams_by_client.get(client_key, 1) - 1
        if remaining <= 0:
            _active_streams_by_client.pop(client_key, None)
        else:
            _active_streams_by_client[client_key] = remaining
