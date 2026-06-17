import type { SignalSnapshot } from "@/lib/types";
import { overallViewColor, scoreBar } from "@/lib/format";

interface Props {
  signals: SignalSnapshot;
  overall: string;
}

export function SignalScores({ signals, overall }: Props) {
  const rows = [
    ["Momentum score", signals.momentum_score],
    ["Trend score", signals.trend_score],
    ["Risk score", signals.risk_score],
    ["Data quality", signals.data_quality_score]
  ] as const;

  return (
    <div className="max-w-[520px] py-4">
      {rows.map(([label, score]) => (
        <div key={label} className="grid grid-cols-[160px_90px_40px] border-b border-border py-2">
          <span className="text-secondary">{label}</span>
          <span className="font-mono text-md">{scoreBar(score)}</span>
          <span className="numeric text-right">{score}/5</span>
        </div>
      ))}
      <div className="mt-5">
        Overall signal: <span style={{ color: overallViewColor(overall) }}>{overall}</span>
      </div>
    </div>
  );
}
