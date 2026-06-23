"use client";

import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";
import { CHART_PALETTE, type ChartSeries } from "./palette";

export function LineSeries<T extends Record<string, unknown>>({
  data,
  series,
  xKey,
  height = 260
}: {
  data: T[];
  series: ChartSeries[];
  xKey: string;
  height?: number;
}) {
  if (!data || data.length === 0) {
    return <div className="empty-chart">Aucune donnee.</div>;
  }
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 12 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey={xKey} angle={data.length > 6 ? -18 : 0} textAnchor={data.length > 6 ? "end" : "middle"} height={data.length > 6 ? 56 : 30} />
        <YAxis />
        <Tooltip />
        <Legend />
        {series.map((entry, idx) => (
          <Line
            key={entry.key}
            type="monotone"
            dataKey={entry.key}
            stroke={entry.color || CHART_PALETTE[idx % CHART_PALETTE.length]}
            dot={false}
            name={entry.label || entry.key}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}
