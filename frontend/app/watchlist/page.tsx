import { ApiUnavailable } from "@/components/layout/ApiUnavailable";
import { WatchlistManager } from "@/components/watchlist/WatchlistManager";
import { ApiError, getWatchlist } from "@/lib/api";

export default async function WatchlistPage() {
  try {
    const items = await getWatchlist();
    return (
      <div className="px-6 py-4">
        <div className="border-b border-border pb-4">
          <div className="text-lg font-medium">Watchlist</div>
          <div className="mt-1 max-w-[620px] text-sm leading-6 text-secondary">
            Save tickers with the reason you are watching, the main risk, and what would change your mind.
          </div>
        </div>

        <div className="max-w-[820px] py-5">
          <WatchlistManager initialItems={items} />
        </div>
      </div>
    );
  } catch (error) {
    if (error instanceof ApiError) {
      return <ApiUnavailable title="Watchlist" message={error.message} />;
    }
    return <ApiUnavailable title="Watchlist" />;
  }
}
