"use client";

import { useMemo, useState } from "react";
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { PricePoint } from "@/lib/types";

const periods = ["1M", "3M", "6M", "1Y", "3Y"] as const;
const limits = { "1M": 21, "3M": 63, "6M": 126, "1Y": 252, "3Y": 756 };

export function PriceChart({ data }: { data: PricePoint[] }) {
  const [period, setPeriod] = useState<(typeof periods)[number]>("1Y");
  const chartData = useMemo(() => data.slice(-limits[period]), [data, period]);

  return (
    <div className="py-4">
      <div className="mb-2 flex justify-end gap-3">
        {periods.map((item) => (
          <button
            key={item}
            onClick={() => setPeriod(item)}
            className={`text-xs ${period === item ? "underline decoration-accent decoration-2 underline-offset-4" : "text-secondary"}`}
          >
            {item}
          </button>
        ))}
      </div>
      <div className="h-[160px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
            <XAxis dataKey="date" tick={{ fontSize: 11, fill: "#8C8A84" }} tickLine={false} axisLine={{ stroke: "#D8D5CE" }} />
            <YAxis
              domain={["dataMin", "dataMax"]}
              tick={{ fontSize: 11, fill: "#8C8A84" }}
              tickLine={false}
              axisLine={{ stroke: "#D8D5CE" }}
              width={48}
            />
            <Tooltip
              contentStyle={{
                borderRadius: 0,
                border: "1px solid #D8D5CE",
                background: "#FFFFFF",
                fontSize: 12,
                boxShadow: "none"
              }}
              formatter={(value) => [Number(value).toFixed(2), "Close"]}
            />
            <Line type="monotone" dataKey="close" stroke="#0B6E4F" strokeWidth={1} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
