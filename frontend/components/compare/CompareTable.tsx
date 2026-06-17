import { fmtPct, maSignalLabel, signalColor } from "@/lib/format";
import type { SignalSnapshot } from "@/lib/types";

const rows: Array<[keyof SignalSnapshot, string, "pct" | "score" | "text"]> = [
  ["return_1m", "1M return", "pct"],
  ["return_3m", "3M return", "pct"],
  ["return_6m", "6M return", "pct"],
  ["return_12m", "12M momentum", "pct"],
  ["volatility_30d", "30d volatility", "pct"],
  ["volatility_90d", "90d volatility", "pct"],
  ["max_drawdown", "Max drawdown", "pct"],
  ["ma_signal", "MA signal", "text"],
  ["momentum_score", "Momentum score", "score"],
  ["trend_score", "Trend score", "score"],
  ["risk_score", "Risk score", "score"]
];

export function CompareTable({ data }: { data: Record<string, SignalSnapshot> }) {
  const tickers = Object.keys(data);

  return (
    <table className="w-full border-collapse text-sm">
      <thead>
        <tr>
          <th className="border border-border px-2 py-2 text-left text-xs uppercase tracking-[0.06em] text-muted">Metric</th>
          {tickers.map((ticker) => (
            <th key={ticker} className="border border-border px-2 py-2 text-left font-mono text-xs uppercase tracking-[0.06em] text-muted">
              {ticker}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map(([key, label, type]) => (
          <tr key={key}>
            <td className="border border-border px-2 py-2 text-secondary">{label}</td>
            {tickers.map((ticker) => {
              const value = data[ticker][key];
              const numeric = Number(value);
              const text =
                type === "pct" ? fmtPct(numeric) : type === "score" ? `${numeric}/5` : maSignalLabel(String(value));
              return (
                <td key={ticker} className="border border-border px-2 py-2 numeric" style={{ color: type === "pct" ? signalColor(numeric) : undefined }}>
                  {text}
                </td>
              );
            })}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
