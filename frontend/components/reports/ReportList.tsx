import Link from "next/link";
import { overallViewColor } from "@/lib/format";
import type { ReportListItem } from "@/lib/types";

function timeLabel(value: string) {
  const date = new Date(value);
  return date.toLocaleString("en-AU", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
}

export function ReportList({ reports }: { reports: ReportListItem[] }) {
  if (reports.length === 0) {
    return <div className="py-4 text-secondary">No reports generated yet.</div>;
  }

  return (
    <div>
      {reports.map((report) => (
        <div key={report.id} className="grid grid-cols-[90px_110px_1fr_90px_60px] gap-4 border-b border-border py-2 text-sm">
          <span className="font-mono">{report.ticker}</span>
          <span className="text-muted">{timeLabel(report.created_at)}</span>
          <span className="truncate">{report.summary}</span>
          <span style={{ color: overallViewColor(report.overall_view) }}>{report.overall_view}</span>
          <Link href={`/research/${report.ticker}`} prefetch={false} className="text-right hover:underline">
            View
          </Link>
        </div>
      ))}
    </div>
  );
}
