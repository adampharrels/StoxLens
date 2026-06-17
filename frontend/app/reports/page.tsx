import { ApiUnavailable } from "@/components/layout/ApiUnavailable";
import { ReportList } from "@/components/reports/ReportList";
import { getReports } from "@/lib/api";

export default async function ReportsPage() {
  try {
    const reports = await getReports();
    return (
      <div className="px-6 py-4">
        <div className="mb-4 text-lg font-medium">Reports</div>
        <ReportList reports={reports} />
      </div>
    );
  } catch {
    return <ApiUnavailable title="Reports" />;
  }
}
