"use client";

import { useMemo, useState } from "react";
import type { MouseEvent } from "react";
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { PricePoint } from "@/lib/types";

const periods = ["1M", "3M", "6M", "1Y"] as const;
const limits = { "1M": 21, "3M": 63, "6M": 126, "1Y": 252 };
const modes = ["Candles", "Line"] as const;

type CandlePoint = PricePoint & {
  open: number;
  high: number;
  low: number;
};

function isCandlePoint(point: PricePoint): point is CandlePoint {
  return point.open !== undefined && point.high !== undefined && point.low !== undefined;
}

function formatPrice(value: number) {
  return value.toLocaleString("en-US", { maximumFractionDigits: 2, minimumFractionDigits: 2 });
}

export function PriceChart({ data }: { data: PricePoint[] }) {
  const [period, setPeriod] = useState<(typeof periods)[number]>("1Y");
  const [mode, setMode] = useState<(typeof modes)[number]>("Candles");
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);
  const chartData = useMemo(() => data.slice(-limits[period]), [data, period]);
  // Candles need full OHLC data. If only closes are available, the component falls back to the line view.
  const candleData = useMemo(() => chartData.filter(isCandlePoint), [chartData]);
  const showCandles = mode === "Candles" && candleData.length > 0;

  const width = 960;
  const height = 260;
  const padding = { top: 16, right: 56, bottom: 28, left: 48 };
  const innerWidth = width - padding.left - padding.right;
  const innerHeight = height - padding.top - padding.bottom;
  const lows = candleData.map((point) => point.low);
  const highs = candleData.map((point) => point.high);
  const minPrice = lows.length ? Math.min(...lows) : 0;
  const maxPrice = highs.length ? Math.max(...highs) : 1;
  const pricePadding = (maxPrice - minPrice || 1) * 0.08;
  const domainMin = minPrice - pricePadding;
  const domainMax = maxPrice + pricePadding;
  const domainSpan = domainMax - domainMin || 1;
  const candleWidth = Math.max(3, Math.min(10, (innerWidth / Math.max(candleData.length, 1)) * 0.62));
  const hovered = hoverIndex === null ? null : candleData[hoverIndex];
  const ticks = Array.from({ length: 5 }, (_, index) => domainMin + (domainSpan / 4) * index).reverse();

  function x(index: number) {
    if (candleData.length <= 1) return padding.left + innerWidth / 2;
    return padding.left + (index / (candleData.length - 1)) * innerWidth;
  }

  function y(value: number) {
    return padding.top + ((domainMax - value) / domainSpan) * innerHeight;
  }

  function onPointerMove(event: MouseEvent<SVGSVGElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    const viewBoxX = ((event.clientX - rect.left) / rect.width) * width;
    const ratio = (viewBoxX - padding.left) / innerWidth;
    const nextIndex = Math.round(ratio * (candleData.length - 1));
    setHoverIndex(Math.max(0, Math.min(candleData.length - 1, nextIndex)));
  }

  return (
    <div className="py-4">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="text-sm font-medium text-primary">Daily Candlestick Chart</div>
          <div className="text-xs text-muted">Saved OHLC candles from the latest full check.</div>
        </div>
        <div className="flex border border-border">
          {modes.map((item) => (
            <button
              key={item}
              onClick={() => setMode(item)}
              className={`h-7 px-3 text-xs ${mode === item ? "bg-primary text-white" : "text-secondary hover:text-primary"}`}
              type="button"
            >
              {item}
            </button>
          ))}
        </div>
        <div className="flex gap-3">
          {periods.map((item) => (
            <button
              key={item}
              onClick={() => setPeriod(item)}
              className={`text-xs ${period === item ? "underline decoration-accent decoration-2 underline-offset-4" : "text-secondary"}`}
              type="button"
            >
              {item}
            </button>
          ))}
        </div>
      </div>
      {chartData.length === 0 ? (
        <div className="flex h-[260px] items-center justify-center border border-border text-sm text-muted">
          No saved daily candles yet. Run Check to fetch OHLC history.
        </div>
      ) : (
        <div className="relative h-[260px]">
          {showCandles ? (
          <>
            {hovered && (
              <div className="absolute left-2 top-2 z-10 border border-border bg-background px-3 py-2 text-xs leading-5">
                <div className="font-medium text-primary">{hovered.date}</div>
                <div className="text-secondary">
                  O {formatPrice(hovered.open)} H {formatPrice(hovered.high)} L {formatPrice(hovered.low)} C{" "}
                  {formatPrice(hovered.close)}
                </div>
              </div>
            )}
            <svg
              aria-label="Daily candlestick chart"
              className="h-full w-full"
              onMouseLeave={() => setHoverIndex(null)}
              onMouseMove={onPointerMove}
              role="img"
              viewBox={`0 0 ${width} ${height}`}
            >
              {ticks.map((tick) => (
                <g key={tick}>
                  <line x1={padding.left} x2={width - padding.right} y1={y(tick)} y2={y(tick)} stroke="#ECE9E3" />
                  <text x={width - padding.right + 8} y={y(tick) + 4} fill="#8C8A84" fontSize="11">
                    {formatPrice(tick)}
                  </text>
                </g>
              ))}
              <line
                x1={padding.left}
                x2={width - padding.right}
                y1={height - padding.bottom}
                y2={height - padding.bottom}
                stroke="#D8D5CE"
              />
              {candleData.map((point, index) => {
                const up = point.close >= point.open;
                const colour = up ? "#0B6E4F" : "#A33A32";
                const bodyTop = y(Math.max(point.open, point.close));
                const bodyHeight = Math.max(2, Math.abs(y(point.open) - y(point.close)));
                return (
                  <g key={`${point.date}-${index}`}>
                    <line x1={x(index)} x2={x(index)} y1={y(point.high)} y2={y(point.low)} stroke={colour} strokeWidth="1.4" />
                    <rect
                      fill={up ? "#0B6E4F" : "#A33A32"}
                      height={bodyHeight}
                      opacity={hoverIndex === null || hoverIndex === index ? 1 : 0.42}
                      width={candleWidth}
                      x={x(index) - candleWidth / 2}
                      y={bodyTop}
                    />
                  </g>
                );
              })}
              {hoverIndex !== null && (
                <line
                  x1={x(hoverIndex)}
                  x2={x(hoverIndex)}
                  y1={padding.top}
                  y2={height - padding.bottom}
                  stroke="#8C8A84"
                  strokeDasharray="4 4"
                />
              )}
              {candleData.length > 0 && (
                <>
                  <text x={padding.left} y={height - 6} fill="#8C8A84" fontSize="11">
                    {candleData[0].date}
                  </text>
                  <text x={width / 2 - 34} y={height - 6} fill="#8C8A84" fontSize="11">
                    {candleData[Math.floor(candleData.length / 2)].date}
                  </text>
                  <text x={width - padding.right - 68} y={height - 6} fill="#8C8A84" fontSize="11">
                    {candleData[candleData.length - 1].date}
                  </text>
                </>
              )}
            </svg>
          </>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
              <XAxis dataKey="date" tick={{ fontSize: 11, fill: "#8C8A84" }} tickLine={false} axisLine={{ stroke: "#D8D5CE" }} />
              <YAxis
                domain={["dataMin", "dataMax"]}
                tick={{ fontSize: 11, fill: "#8C8A84" }}
                tickLine={false}
                axisLine={{ stroke: "#D8D5CE" }}
                width={48}
              />
              <Tooltip
                contentStyle={{
                  borderRadius: 0,
                  border: "1px solid #D8D5CE",
                  background: "#FFFFFF",
                  fontSize: 12,
                  boxShadow: "none"
                }}
                formatter={(value) => [Number(value).toFixed(2), "Close"]}
              />
              <Line type="monotone" dataKey="close" stroke="#0B6E4F" strokeWidth={1} dot={false} />
            </LineChart>
          </ResponsiveContainer>
          )}
        </div>
      )}
    </div>
  );
}
