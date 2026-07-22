export const fmtPct = (n: number) => (n >= 0 ? "+" : "") + (n * 100).toFixed(1) + "%";

export const fmtNum = (n: number, dp = 1) => n.toFixed(dp);

export const fmtMoney = (n: number) => "A$" + n.toFixed(2);

export const fmtCompactNumber = (n: number): string =>
  new Intl.NumberFormat("en-AU", {
    notation: "compact",
    maximumFractionDigits: 1
  }).format(n);

export const fmtCompactMoney = (n: number, currency = ""): string => {
  const prefix = currency ? `${currency} ` : "";
  return `${prefix}${fmtCompactNumber(n)}`;
};

export const signalColor = (n: number): string => (n > 0 ? "#0B6E4F" : n < 0 ? "#C0392B" : "#1A1916");

export const signalArrow = (n: number): string => (n > 0.005 ? "↑" : n < -0.005 ? "↓" : "→");

export const overallViewColor = (v: string): string =>
  ({
    Watchlist: "#0B6E4F",
    "Needs Review": "#B07D1A",
    "Weak Signal": "#C0392B"
  })[v] ?? "#1A1916";

export const scoreBar = (score: number, max = 5): string => "█".repeat(score) + "░".repeat(max - score);

export const maSignalLabel = (value: string) =>
  ({
    above_both: "Above 50d and 200d",
    above_50_only: "Above 50d only",
    below_both: "Below 50d and 200d"
  })[value] ?? value;
