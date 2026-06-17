export function ApiUnavailable({ title }: { title: string }) {
  return (
    <div className="px-6 py-4">
      <div className="mb-2 text-lg font-medium">{title}</div>
      <div className="border-t border-border pt-3 text-sm text-secondary">
        Backend unavailable. Start the FastAPI service on port 8000 to load live data.
      </div>
    </div>
  );
}
