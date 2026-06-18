import type { SignalSnapshot } from "@/lib/types";
import { fmtNum, fmtPct, maSignalLabel, signalArrow, signalColor } from "@/lib/format";

const pctRows: Array<[keyof SignalSnapshot, string]> = [
  ["return_1m", "1M return"],
  ["return_3m", "3M return"],
  ["return_6m", "6M return"],
  ["return_12m", "12M momentum"],
  ["volatility_30d", "30d volatility"],
  ["volatility_90d", "90d volatility"],
  ["max_drawdown", "Max drawdown"]
];

interface Props {
  signals: SignalSnapshot;
  dataSource?: string;
  fetchedAt?: string;
  tradingDays?: number;
  promptVersion?: string;
  modelUsed?: string;
}

function fetchedLabel(value?: string) {
  if (!value) return "Unavailable";
  return new Date(value).toLocaleString("en-AU", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit"
  });
}

function tradingDaysLabel(value?: number) {
  return typeof value === "number" ? value.toLocaleString() : "Unavailable";
}

export function MetricsTable({ signals, dataSource, fetchedAt, tradingDays, promptVersion, modelUsed }: Props) {
  return (
    <div className="max-w-[620px] py-4">
      {pctRows.map(([key, label]) => {
        const value = Number(signals[key]);
        const isReturn = key.toString().startsWith("return") || key === "max_drawdown";
        const color = isReturn ? signalColor(value) : undefined;
        return (
          <div key={key} className="flex justify-between border-b border-border py-2">
            <span className="text-secondary">{label}</span>
            <span className="numeric" style={{ color }}>
              {fmtPct(value)} {isReturn ? signalArrow(value) : ""}
            </span>
          </div>
        );
      })}
      <div className="flex justify-between border-b border-border py-2">
        <span className="text-secondary">RSI (14)</span>
        <span className="numeric">{fmtNum(signals.rsi)}</span>
      </div>
      <div className="flex justify-between border-b border-border py-2">
        <span className="text-secondary">MA signal</span>
        <span>{maSignalLabel(signals.ma_signal)}</span>
      </div>
      <div className="flex justify-between border-b border-border py-2">
        <span className="text-secondary">Volume trend</span>
        <span className="numeric" style={{ color: signalColor(signals.volume_trend) }}>
          {fmtPct(signals.volume_trend)} vs 90d avg
        </span>
      </div>
      <div className="mt-5 border-t border-border pt-3 text-xs text-muted">
        Source: {dataSource ?? "Unavailable"} · Fetched: {fetchedLabel(fetchedAt)} · {tradingDaysLabel(tradingDays)} trading days ·
        Prompt: {promptVersion ?? "Unavailable"} · Model: {modelUsed ?? "Unavailable"}
      </div>
    </div>
  );
}
