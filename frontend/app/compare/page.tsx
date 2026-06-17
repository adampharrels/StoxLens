import { CompareTable } from "@/components/compare/CompareTable";
import { ApiUnavailable } from "@/components/layout/ApiUnavailable";
import { ApiError, getCompare } from "@/lib/api";

export default async function ComparePage() {
  try {
    const data = await getCompare();
    return (
      <div className="px-6 py-4">
        <div className="mb-4 text-lg font-medium">Compare</div>
        <CompareTable data={data} />
      </div>
    );
  } catch (error) {
    if (error instanceof ApiError) {
      return <ApiUnavailable title="Compare" message={error.message} />;
    }
    return <ApiUnavailable title="Compare" />;
  }
}
