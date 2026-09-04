import { ApiUnavailable } from "@/components/layout/ApiUnavailable";
import { TodayTriageClient } from "@/components/triage/TodayTriageClient";
import { ApiError, getTriage } from "@/lib/api";

export default async function TodayPage() {
  try {
    const data = await getTriage();
    return <TodayTriageClient initialData={data} />;
  } catch (error) {
    if (error instanceof ApiError) {
      return <ApiUnavailable title="Today" message={error.message} />;
    }
    return <ApiUnavailable title="Today" />;
  }
}
