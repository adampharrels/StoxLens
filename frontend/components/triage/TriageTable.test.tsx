import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { TriageTable } from "@/components/triage/TriageTable";
import type { TriageItem } from "@/lib/types";

afterEach(cleanup);

function scoredItem(overrides: Partial<TriageItem> = {}): TriageItem {
  return {
    ticker: "MSFT",
    status: "ok",
    issue_message: null,
    last_checked_at: "2026-11-18T00:00:00Z",
    attention_score: 60,
    severity: "High",
    price: 410.5,
    price_change_pct: -0.031,
    as_of_date: "2026-11-17",
    reasons: [
      { code: "drawdown", label: "Large drawdown", detail: "Price is -22.0% below its 252-day high.", impact: 3 },
      { code: "volume_surge", label: "Volume surge", detail: "Latest volume is 1.8x the 90-day average.", impact: 2 }
    ],
    news: [],
    metrics: { rsi: 41.2, volatility_percentile: 0.5, volume_ratio: 1.8 },
    watch_note: { ticker: "MSFT", watch_reason: "", main_risk: "", change_my_mind: "" },
    changes: null,
    ...overrides
  };
}

describe("TriageTable", () => {
  it("shows an empty state when there are no items", () => {
    render(<TriageTable items={[]} />);
    expect(screen.getByText(/No watchlist tickers need attention/)).toBeTruthy();
  });

  it("shows each reason's contribution to the 0-100 score", () => {
    render(<TriageTable items={[scoredItem()]} />);

    expect(screen.getByText("Score 60/100")).toBeTruthy();
    expect(screen.getByText("+36")).toBeTruthy();
    expect(screen.getByText("+24")).toBeTruthy();
    expect(screen.getByText("RSI 41.2 · Vol pct 50 · Volume 1.8x")).toBeTruthy();
  });

  it("separates tickers with data issues from scored tickers", () => {
    const issue = scoredItem({
      ticker: "BHP.AX",
      status: "data_issue",
      issue_message: "Provider could not return enough price history.",
      attention_score: null,
      severity: null,
      price: null,
      price_change_pct: null,
      reasons: []
    });
    render(<TriageTable items={[scoredItem(), issue]} />);

    expect(screen.getByText("Needs check / Data issues")).toBeTruthy();
    expect(screen.getByText("Data issue")).toBeTruthy();
    expect(screen.getByText("Provider could not return enough price history.")).toBeTruthy();
  });

  it("turns the user's change-my-mind note into the research question", () => {
    const item = scoredItem({
      watch_note: {
        ticker: "MSFT",
        watch_reason: "Azure growth is reaccelerating.",
        main_risk: "",
        change_my_mind: "Azure growth drops below 20%."
      }
    });
    render(<TriageTable items={[item]} />);

    expect(screen.getByText("Is this alert evidence that azure growth drops below 20%?")).toBeTruthy();
    expect(screen.getByText("Large drawdown: Price is -22.0% below its 252-day high.")).toBeTruthy();
  });
});
