"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  Legend,
  XAxis,
  YAxis
} from "recharts";
import { CHART_PALETTE, type ChartSeries } from "./palette";

export function BarSeries<T extends Record<string, unknown>>({
  data,
  series,
  xKey,
  height = 260,
  stacked = false
}: {
  data: T[];
  series: ChartSeries[];
  xKey: string;
  height?: number;
  stacked?: boolean;
}) {
  if (!data || data.length === 0) {
    return <div className="empty-chart">Aucune donnee.</div>;
  }
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 12 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey={xKey} angle={data.length > 6 ? -18 : 0} textAnchor={data.length > 6 ? "end" : "middle"} height={data.length > 6 ? 56 : 30} />
        <YAxis />
        <Tooltip />
        <Legend />
        {series.map((entry, idx) => (
          <Bar
            key={entry.key}
            dataKey={entry.key}
            stackId={stacked ? "stack" : undefined}
            fill={entry.color || CHART_PALETTE[idx % CHART_PALETTE.length]}
            name={entry.label || entry.key}
            radius={[4, 4, 0, 0]}
          />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}
