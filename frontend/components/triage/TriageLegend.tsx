import { AlertTriangle, CircleCheck, CircleDot } from "lucide-react";

const severity = [
  { label: "High", range: "60-100", icon: AlertTriangle, className: "text-red-600" },
  { label: "Medium", range: "30-59", icon: CircleDot, className: "text-amber-600" },
  { label: "Low", range: "0-29", icon: CircleCheck, className: "text-secondary" }
];

const impacts = [
  { label: "Major", value: "+48", detail: "earnings, guidance, regulatory, 200D break" },
  { label: "Strong", value: "+36", detail: "50D break, drawdown, volatility spike" },
  { label: "Moderate", value: "+24", detail: "abnormal volume, analyst, data quality" },
  { label: "Minor", value: "+12", detail: "product or contract news" }
];

export function TriageLegend() {
  return (
    <div className="mb-5 grid max-w-[980px] grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)] gap-6 border-t border-border pt-4">
      <div>
        <div className="label mb-2">Severity</div>
        <div className="grid grid-cols-3 gap-3">
          {severity.map((item) => {
            const Icon = item.icon;
            return (
              <div key={item.label} className="border border-border px-3 py-2">
                <div className={`inline-flex items-center gap-2 text-sm font-medium ${item.className}`}>
                  <Icon className="h-4 w-4" />
                  {item.label}
                </div>
                <div className="mt-1 numeric text-xs text-muted">{item.range}</div>
              </div>
            );
          })}
        </div>
      </div>

      <div>
        <div className="label mb-2">Score</div>
        <div className="border border-border">
          <div className="border-b border-border px-3 py-2 text-sm text-secondary">
            Score = trigger impact total x 12, capped at 100.
          </div>
          <div className="grid grid-cols-4">
            {impacts.map((item) => (
              <div key={item.label} className="border-r border-border px-3 py-2 last:border-r-0">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-medium">{item.label}</span>
                  <span className="numeric text-xs text-muted">{item.value}</span>
                </div>
                <div className="mt-1 text-xs leading-5 text-secondary">{item.detail}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
