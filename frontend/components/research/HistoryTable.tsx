import type { PricePoint } from "@/lib/types";

export function HistoryTable({ data }: { data: PricePoint[] }) {
  return (
    <table className="w-full border-collapse text-sm">
      <thead>
        <tr className="border-b border-border text-left text-xs uppercase tracking-[0.06em] text-muted">
          <th className="py-2 font-normal">Date</th>
          <th className="py-2 font-normal">Open</th>
          <th className="py-2 font-normal">High</th>
          <th className="py-2 font-normal">Low</th>
          <th className="py-2 font-normal">Close</th>
          <th className="py-2 font-normal">Volume</th>
          <th className="py-2 font-normal">Adj Close</th>
        </tr>
      </thead>
      <tbody>
        {data
          .slice(-40)
          .reverse()
          .map((row) => (
            <tr key={row.date} className="border-b border-border font-mono numeric text-sm">
              <td className="py-2">{row.date}</td>
              <td className="py-2">{row.open?.toFixed(2)}</td>
              <td className="py-2">{row.high?.toFixed(2)}</td>
              <td className="py-2">{row.low?.toFixed(2)}</td>
              <td className="py-2">{row.close.toFixed(2)}</td>
              <td className="py-2">{row.volume?.toLocaleString()}</td>
              <td className="py-2">{row.adj_close?.toFixed(2)}</td>
            </tr>
          ))}
      </tbody>
    </table>
  );
}
