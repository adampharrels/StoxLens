import { describe, expect, it } from "vitest";
import { fmtCompactMoney, fmtPct, maSignalLabel, overallViewColor, scoreBar, signalArrow } from "@/lib/format";

describe("fmtPct", () => {
  it("prefixes non-negative values with a plus sign", () => {
    expect(fmtPct(0.1234)).toBe("+12.3%");
    expect(fmtPct(0)).toBe("+0.0%");
  });

  it("keeps the minus sign for negative values", () => {
    expect(fmtPct(-0.25)).toBe("-25.0%");
  });
});

describe("fmtCompactMoney", () => {
  it("adds the currency code only when one is given", () => {
    expect(fmtCompactMoney(1_500_000_000, "USD")).toBe("USD 1.5B");
    expect(fmtCompactMoney(2_000)).toBe("2K");
  });
});

describe("signalArrow", () => {
  it("treats moves within half a percent as flat", () => {
    expect(signalArrow(0.004)).toBe("→");
    expect(signalArrow(-0.004)).toBe("→");
    expect(signalArrow(0.006)).toBe("↑");
    expect(signalArrow(-0.006)).toBe("↓");
  });
});

describe("scoreBar", () => {
  it("fills one block per point out of the max", () => {
    expect(scoreBar(3)).toBe("███░░");
    expect(scoreBar(2, 4)).toBe("██░░");
  });
});

describe("label lookups", () => {
  it("maps known moving-average states and passes unknown ones through", () => {
    expect(maSignalLabel("above_50_only")).toBe("Above 50d only");
    expect(maSignalLabel("sideways")).toBe("sideways");
  });

  it("falls back to the neutral colour for unknown views", () => {
    expect(overallViewColor("Watchlist")).toBe("#0B6E4F");
    expect(overallViewColor("Unknown")).toBe("#1A1916");
  });
});
