import { fmtMoney, fmtPct, signalArrow, signalColor } from "@/lib/format";

interface Props {
  companyName: string;
  ticker: string;
  exchange: string;
  sector: string;
  price: number;
  priceChangePct: number;
}

export function CompanyRow({ companyName, ticker, exchange, sector, price, priceChangePct }: Props) {
  return (
    <div className="flex items-baseline gap-4 py-3">
      <div className="text-md font-medium">{companyName}</div>
      <div className="text-sm text-muted">
        {ticker} · {exchange || "Market"} · {sector}
      </div>
      <div className="ml-auto flex items-baseline gap-3 numeric">
        <span>{fmtMoney(price)}</span>
        <span style={{ color: signalColor(priceChangePct) }}>{fmtPct(priceChangePct)}</span>
        <span style={{ color: signalColor(priceChangePct) }}>{signalArrow(priceChangePct)}</span>
      </div>
    </div>
  );
}
