"use client";

import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { CHART_PALETTE } from "./palette";

export function PieSeries<T extends Record<string, unknown>>({
  data,
  dataKey,
  nameKey,
  height = 260,
  innerRadius = 48,
  outerRadius = 92
}: {
  data: T[];
  dataKey: string;
  nameKey: string;
  height?: number;
  innerRadius?: number;
  outerRadius?: number;
}) {
  if (!data || data.length === 0) {
    return <div className="empty-chart">Aucune donnee.</div>;
  }
  return (
    <ResponsiveContainer width="100%" height={height}>
      <PieChart margin={{ top: 8, right: 16, left: 16, bottom: 8 }}>
        <Tooltip />
        <Legend />
        <Pie
          data={data}
          dataKey={dataKey}
          nameKey={nameKey}
          outerRadius={outerRadius}
          innerRadius={innerRadius}
          paddingAngle={2}
        >
          {data.map((_, idx) => (
            <Cell key={idx} fill={CHART_PALETTE[idx % CHART_PALETTE.length]} />
          ))}
        </Pie>
      </PieChart>
    </ResponsiveContainer>
  );
}
