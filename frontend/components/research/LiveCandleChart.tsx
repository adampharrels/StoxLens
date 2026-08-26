"use client";

import { useEffect, useMemo, useState } from "react";
import { getLiveCandleStreamUrl } from "@/lib/api";
import type { LiveCandle, LiveStreamError, LiveStreamStatus } from "@/lib/types";

type StreamMessage = LiveCandle | LiveStreamStatus | LiveStreamError;

function formatPrice(value: number) {
  return value.toLocaleString("en-US", { maximumFractionDigits: 2, minimumFractionDigits: 2 });
}

function formatTime(value: string) {
  return new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function upsertCandle(candles: LiveCandle[], candle: LiveCandle) {
  const existingIndex = candles.findIndex((item) => item.timestamp === candle.timestamp);
  if (existingIndex >= 0) {
    return candles.map((item, index) => (index === existingIndex ? candle : item));
  }
  return [...candles, candle].slice(-60);
}

function errorLabel(message: LiveStreamError) {
  const source = message.source ? `${message.source}` : "backend";
  const code = message.code ? ` ${message.code}` : "";
  return `${source}${code}: ${message.message}`;
}

export function LiveCandleChart({ ticker }: { ticker: string }) {
  const [candles, setCandles] = useState<LiveCandle[]>([]);
  const [status, setStatus] = useState("Live stream idle. Start when you need live minute bars.");
  const [error, setError] = useState<string | null>(null);
  const [streamingTicker, setStreamingTicker] = useState<string | null>(null);
  const isStreaming = streamingTicker === ticker;

  useEffect(() => {
    setCandles([]);
    setError(null);
    setStreamingTicker(null);
    setStatus("Live stream idle. Start when you need live minute bars.");
  }, [ticker]);

  useEffect(() => {
    if (streamingTicker !== ticker) return;

    setError(null);
    setStatus("Connecting to Alpaca live candles.");
    let closedByComponent = false;
    const activeTicker = streamingTicker;

    // The browser connects to our backend proxy so Alpaca keys never enter the client bundle.
    const socket = new WebSocket(getLiveCandleStreamUrl(activeTicker));

    socket.onopen = () => setStatus("Connected to backend. Waiting for Alpaca.");
    socket.onmessage = (event) => {
      let message: StreamMessage;
      try {
        message = JSON.parse(event.data) as StreamMessage;
      } catch {
        setError("Live candle stream sent an invalid message.");
        return;
      }
      if (message.type === "bar") {
        setCandles((current) => upsertCandle(current, message));
        setStatus(`Live from ${message.source}.`);
        return;
      }
      if (message.type === "error") {
        setError(errorLabel(message));
        setStreamingTicker((current) => (current === activeTicker ? null : current));
        return;
      }
      setStatus(message.message);
    };
    socket.onerror = () => {
      setError("Live candle stream failed.");
      setStreamingTicker((current) => (current === activeTicker ? null : current));
    };
    socket.onclose = () => {
      if (!closedByComponent) {
        setStatus("Live candle stream closed.");
        setStreamingTicker((current) => (current === activeTicker ? null : current));
      }
    };

    return () => {
      closedByComponent = true;
      socket.close();
    };
  }, [ticker, streamingTicker]);

  const chart = useMemo(() => {
    const width = 960;
    const height = 220;
    const padding = { top: 14, right: 52, bottom: 28, left: 48 };
    const innerWidth = width - padding.left - padding.right;
    const innerHeight = height - padding.top - padding.bottom;
    const minPrice = candles.length ? Math.min(...candles.map((item) => item.low)) : 0;
    const maxPrice = candles.length ? Math.max(...candles.map((item) => item.high)) : 1;
    const pricePadding = (maxPrice - minPrice || 1) * 0.08;
    const domainMin = minPrice - pricePadding;
    const domainMax = maxPrice + pricePadding;
    const domainSpan = domainMax - domainMin || 1;
    const candleWidth = Math.max(5, Math.min(14, (innerWidth / Math.max(candles.length, 1)) * 0.55));
    const ticks = Array.from({ length: 4 }, (_, index) => domainMin + (domainSpan / 3) * index).reverse();

    const x = (index: number) => {
      if (candles.length <= 1) return padding.left + innerWidth / 2;
      return padding.left + (index / (candles.length - 1)) * innerWidth;
    };

    const y = (value: number) => padding.top + ((domainMax - value) / domainSpan) * innerHeight;

    return { candleWidth, height, padding, ticks, width, x, y };
  }, [candles]);

  return (
    <section className="border-b border-border py-4">
      <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="text-sm font-medium text-primary">Live Alpaca Candles</div>
          <div className="text-xs text-muted">Start the stream only when you need live Alpaca minute bars.</div>
        </div>
        <div className="flex items-center gap-3">
          <div className={`text-xs ${error ? "text-red-600" : "text-muted"}`}>{error ?? status}</div>
          {isStreaming ? (
            <button
              className="h-8 border border-border px-3 text-sm text-primary hover:border-accent"
              onClick={() => {
                setStreamingTicker(null);
                setStatus("Live stream stopped. Last received candles remain visible.");
              }}
              type="button"
            >
              Stop
            </button>
          ) : (
            <button
              className="h-8 border border-border px-3 text-sm text-primary hover:border-accent"
              onClick={() => {
                setCandles([]);
                setError(null);
                setStreamingTicker(ticker);
              }}
              type="button"
            >
              Start live stream
            </button>
          )}
        </div>
      </div>

      {candles.length === 0 ? (
        <div className="flex h-[220px] flex-col items-center justify-center border border-border px-4 text-center">
          <div className={`text-sm ${error ? "text-red-600" : "text-muted"}`}>{error ?? status}</div>
          {!error && isStreaming && (
            <div className="mt-2 max-w-[420px] text-xs leading-5 text-muted">
              Alpaca sends live candles as minute bars. If the US market is closed, or no new minute bar has arrived yet,
              this panel can stay empty while the WebSocket remains connected.
            </div>
          )}
          {!error && !isStreaming && (
            <div className="mt-2 max-w-[420px] text-xs leading-5 text-muted">
              Saved research stays loaded without opening an Alpaca connection.
            </div>
          )}
        </div>
      ) : (
        <svg aria-label="Live Alpaca candlestick chart" className="h-[220px] w-full" role="img" viewBox={`0 0 ${chart.width} ${chart.height}`}>
          {chart.ticks.map((tick) => (
            <g key={tick}>
              <line x1={chart.padding.left} x2={chart.width - chart.padding.right} y1={chart.y(tick)} y2={chart.y(tick)} stroke="#ECE9E3" />
              <text x={chart.width - chart.padding.right + 8} y={chart.y(tick) + 4} fill="#8C8A84" fontSize="11">
                {formatPrice(tick)}
              </text>
            </g>
          ))}
          {candles.map((candle, index) => {
            const up = candle.close >= candle.open;
            const color = up ? "#0B6E4F" : "#A33A32";
            const bodyTop = chart.y(Math.max(candle.open, candle.close));
            const bodyHeight = Math.max(2, Math.abs(chart.y(candle.open) - chart.y(candle.close)));
            return (
              <g key={candle.timestamp}>
                <line x1={chart.x(index)} x2={chart.x(index)} y1={chart.y(candle.high)} y2={chart.y(candle.low)} stroke={color} strokeWidth="1.4" />
                <rect fill={color} height={bodyHeight} width={chart.candleWidth} x={chart.x(index) - chart.candleWidth / 2} y={bodyTop} />
              </g>
            );
          })}
          <text x={chart.padding.left} y={chart.height - 6} fill="#8C8A84" fontSize="11">
            {formatTime(candles[0].timestamp)}
          </text>
          <text x={chart.width - chart.padding.right - 44} y={chart.height - 6} fill="#8C8A84" fontSize="11">
            {formatTime(candles[candles.length - 1].timestamp)}
          </text>
        </svg>
      )}
    </section>
  );
}
