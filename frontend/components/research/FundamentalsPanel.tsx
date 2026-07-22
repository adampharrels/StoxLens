import type { Fundamentals } from "@/lib/types";
import { fmtCompactMoney, fmtNum, fmtPct } from "@/lib/format";

interface Props {
  fundamentals: Fundamentals;
  currency: string;
  industry: string;
}

function valueOrUnavailable(value: number | null | undefined, format: (value: number) => string) {
  return typeof value === "number" && Number.isFinite(value) ? format(value) : "Unavailable";
}

export function FundamentalsPanel({ fundamentals, currency, industry }: Props) {
  const rows = [
    ["Market cap", valueOrUnavailable(fundamentals.market_cap, (value) => fmtCompactMoney(value, currency))],
    ["P/E ratio", valueOrUnavailable(fundamentals.pe_ratio, (value) => fmtNum(value, 1))],
    ["EPS", valueOrUnavailable(fundamentals.eps, (value) => fmtNum(value, 2))],
    ["Revenue TTM", valueOrUnavailable(fundamentals.revenue_ttm, (value) => fmtCompactMoney(value, currency))],
    ["Revenue growth YoY", valueOrUnavailable(fundamentals.revenue_growth_yoy, fmtPct)],
    ["Profit margin", valueOrUnavailable(fundamentals.profit_margin, fmtPct)],
    ["Debt/equity", valueOrUnavailable(fundamentals.debt_to_equity, (value) => fmtNum(value, 2))],
    ["Dividend yield", valueOrUnavailable(fundamentals.dividend_yield, fmtPct)]
  ];

  return (
    <section className="mt-4 max-w-[620px] border-t border-border pt-4">
      <div className="mb-3 flex items-baseline justify-between gap-4">
        <h2 className="text-sm font-medium uppercase tracking-[0.14em] text-secondary">Fundamentals</h2>
        <span className="text-xs text-muted">{industry || "Industry unavailable"}</span>
      </div>
      <div className="grid grid-cols-2 gap-x-6">
        {rows.map(([label, value]) => (
          <div key={label} className="flex justify-between border-b border-border py-2 text-sm">
            <span className="text-secondary">{label}</span>
            <span className="numeric text-primary">{value}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
