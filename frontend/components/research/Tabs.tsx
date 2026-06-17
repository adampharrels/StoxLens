"use client";

const tabs = ["Overview", "Signals", "AI Brief", "History"] as const;

export type ResearchTab = (typeof tabs)[number];

export function Tabs({ active, onChange }: { active: ResearchTab; onChange: (tab: ResearchTab) => void }) {
  return (
    <div className="flex border-b border-border">
      {tabs.map((tab) => (
        <button
          key={tab}
          onClick={() => onChange(tab)}
          className={`border-b-2 px-0 pb-2 pt-1 mr-6 text-sm ${
            active === tab ? "border-accent text-primary" : "border-transparent text-secondary"
          }`}
        >
          {tab}
        </button>
      ))}
    </div>
  );
}
