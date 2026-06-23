"use client";

import type { ComponentType } from "react";

export function KpiCard({
  label,
  value,
  trend,
  icon: Icon,
  hint
}: {
  label: string;
  value: React.ReactNode;
  trend?: { delta: number; suffix?: string };
  icon?: ComponentType<{ size?: number }>;
  hint?: string;
}) {
  const trendClass = trend ? (trend.delta > 0 ? "kpi-trend up" : trend.delta < 0 ? "kpi-trend down" : "kpi-trend") : undefined;
  return (
    <article className="metric-card">
      <header>
        <span className="muted">{label}</span>
        {Icon ? <Icon size={18} /> : null}
      </header>
      <strong className="tabular">{value}</strong>
      {trend ? (
        <span className={trendClass}>
          {trend.delta > 0 ? "+" : ""}
          {trend.delta}
          {trend.suffix || ""}
        </span>
      ) : null}
      {hint ? <small className="muted">{hint}</small> : null}
    </article>
  );
}
