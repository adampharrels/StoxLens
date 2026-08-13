import { TriageTable } from "@/components/triage/TriageTable";
import { TriageLegend } from "@/components/triage/TriageLegend";
import { ApiUnavailable } from "@/components/layout/ApiUnavailable";
import { ApiError, getTriage } from "@/lib/api";

function generatedLabel(value: string) {
  return new Date(value).toLocaleString("en-AU", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit"
  });
}

export default async function TodayPage() {
  try {
    const data = await getTriage();
    const highCount = data.items.filter((item) => item.severity === "High").length;
    const mediumCount = data.items.filter((item) => item.severity === "Medium").length;

    return (
      <div className="px-6 py-4">
        <div className="border-b border-border pb-4">
          <div className="text-lg font-medium">Today</div>
          <div className="mt-1 max-w-[620px] text-sm leading-6 text-secondary">Watchlist names sorted by attention urgency.</div>
        </div>

        <div className="grid max-w-[820px] grid-cols-3 gap-6 py-5">
          <div>
            <div className="label">High</div>
            <div className="mt-1 numeric text-xl">{highCount}</div>
          </div>
          <div>
            <div className="label">Medium</div>
            <div className="mt-1 numeric text-xl">{mediumCount}</div>
          </div>
          <div>
            <div className="label">Generated</div>
            <div className="mt-1 text-sm">{generatedLabel(data.generated_at)}</div>
          </div>
        </div>

        <TriageLegend />
        <TriageTable items={data.items} />
      </div>
    );
  } catch (error) {
    if (error instanceof ApiError) {
      return <ApiUnavailable title="Today" message={error.message} />;
    }
    return <ApiUnavailable title="Today" />;
  }
}
