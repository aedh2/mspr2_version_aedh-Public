"use client";

import Link from "next/link";
import type { CSSProperties, ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import { ChevronRight, Database } from "lucide-react";
import { formatNumber } from "@/src/lib/format";

type Tone = "blue" | "teal" | "green" | "amber" | "red" | "violet";

const toneColors: Record<Tone, string> = {
  blue: "#2563eb",
  teal: "#0284c7",
  green: "#1d4ed8",
  amber: "#b54708",
  red: "#b42318",
  violet: "#4f46e5"
};

function clampScore(value?: number | null) {
  if (value === null || value === undefined || Number.isNaN(value)) return null;
  return Math.max(0, Math.min(100, Math.round(value)));
}

export function HealthKpiCard({
  label,
  value,
  hint,
  icon: Icon,
  tone = "teal",
  href
}: {
  label: string;
  value: ReactNode;
  hint?: string;
  icon?: LucideIcon;
  tone?: Tone;
  href?: string;
}) {
  const content = (
    <>
      <div className="health-kpi-main">
        <span>{label}</span>
        <strong>{value ?? "N/A"}</strong>
        {hint ? <small>{hint}</small> : null}
      </div>
      {Icon ? (
        <span className="health-kpi-icon" style={{ "--kpi-color": toneColors[tone] } as CSSProperties}>
          <Icon size={19} aria-hidden />
        </span>
      ) : null}
    </>
  );

  if (!href) {
    return <article className="health-kpi-card">{content}</article>;
  }

  return (
    <Link href={href} className="health-kpi-card health-kpi-card-link">
      {content}
    </Link>
  );
}

export function CircularScore({
  label,
  value,
  helper,
  tone = "teal"
}: {
  label: string;
  value?: number | null;
  helper?: string;
  tone?: Tone;
}) {
  const score = clampScore(value);
  const ariaLabel = score === null ? `${label}: donnee indisponible` : `${label}: ${score} sur 100`;

  return (
    <article className="circular-score-card" aria-label={ariaLabel}>
      <div
        className="circular-score-ring"
        style={{
          "--score": String(score ?? 0),
          "--score-color": toneColors[tone]
        } as CSSProperties}
        aria-hidden="true"
      >
        <span>{score === null ? "N/A" : score}</span>
      </div>
      <div>
        <strong>{label}</strong>
        {helper ? <span>{helper}</span> : null}
      </div>
    </article>
  );
}

export function HealthProgress({
  label,
  value,
  helper,
  tone = "teal"
}: {
  label: string;
  value?: number | null;
  helper?: string;
  tone?: Tone;
}) {
  const score = clampScore(value);
  return (
    <div className="health-progress">
      <div>
        <span>{label}</span>
        <strong>{score === null ? "Indisponible" : `${score}%`}</strong>
      </div>
      <div
        className="health-progress-track"
        role="meter"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={score ?? undefined}
      >
        <span
          style={{
            width: `${score ?? 0}%`,
            "--progress-color": toneColors[tone]
          } as CSSProperties}
        />
      </div>
      {helper ? <small>{helper}</small> : null}
    </div>
  );
}

export type DonutItem = {
  label: string;
  value: number;
  color?: string;
};

export function CompactDonut({
  label,
  items,
  emptyLabel = "Donnees indisponibles"
}: {
  label: string;
  items: DonutItem[];
  emptyLabel?: string;
}) {
  const cleanItems = items.filter((item) => item.value > 0);
  const total = cleanItems.reduce((sum, item) => sum + item.value, 0);
  const gradient = total
    ? cleanItems
        .reduce<{ cursor: number; parts: string[] }>(
          (acc, item, index) => {
            const color = item.color || defaultDonutColor(index);
            const next = acc.cursor + (item.value / total) * 100;
            acc.parts.push(`${color} ${acc.cursor}% ${next}%`);
            acc.cursor = next;
            return acc;
          },
          { cursor: 0, parts: [] }
        )
        .parts.join(", ")
    : "#eef2f6 0% 100%";

  return (
    <article className="compact-donut-card">
      <div
        className="compact-donut"
        style={{ "--donut-gradient": gradient } as CSSProperties}
        role="img"
        aria-label={total ? `${label}: ${total} elements` : `${label}: ${emptyLabel}`}
      >
        <span>{total || "N/A"}</span>
      </div>
      <div className="compact-donut-content">
        <strong>{label}</strong>
        {total ? (
          <div className="compact-donut-legend">
            {cleanItems.slice(0, 5).map((item, index) => (
              <span key={item.label}>
                <i style={{ background: item.color || defaultDonutColor(index) }} aria-hidden="true" />
                {item.label}: {item.value}
              </span>
            ))}
          </div>
        ) : (
          <small>{emptyLabel}</small>
        )}
      </div>
    </article>
  );
}

export type HealthTimelineItem = {
  id: string;
  label: string;
  title: string;
  meta?: string;
  date?: string | null;
  href?: string;
  icon?: LucideIcon;
};

export function HealthTimeline({ items, emptyLabel }: { items: HealthTimelineItem[]; emptyLabel: string }) {
  if (!items.length) {
    return (
      <div className="health-empty-inline">
        <Database size={18} aria-hidden />
        <span>{emptyLabel}</span>
      </div>
    );
  }

  return (
    <ol className="health-timeline">
      {items.map((item) => {
        const Icon = item.icon;
        const content = (
          <>
            <span className="health-timeline-icon">{Icon ? <Icon size={15} aria-hidden /> : null}</span>
            <span className="health-timeline-copy">
              <small>{item.label}</small>
              <strong>{item.title}</strong>
              {item.meta ? <em>{item.meta}</em> : null}
            </span>
            {item.href ? <ChevronRight size={15} aria-hidden /> : null}
          </>
        );

        return (
          <li key={item.id}>
            {item.href ? (
              <Link href={item.href} className="health-timeline-row">
                {content}
              </Link>
            ) : (
              <div className="health-timeline-row">{content}</div>
            )}
          </li>
        );
      })}
    </ol>
  );
}

export function DashboardSkeleton() {
  return (
    <div className="dashboard-skeleton" aria-label="Chargement du tableau de bord">
      <div className="skeleton skeleton-hero" />
      <div className="skeleton-grid">
        {Array.from({ length: 8 }).map((_, index) => (
          <div className="skeleton skeleton-card" key={index} />
        ))}
      </div>
      <div className="skeleton-grid skeleton-grid-wide">
        <div className="skeleton skeleton-panel" />
        <div className="skeleton skeleton-panel" />
      </div>
    </div>
  );
}

export function formatScore(value?: number | null) {
  const score = clampScore(value);
  return score === null ? "N/A" : formatNumber(score, " /100");
}

function defaultDonutColor(index: number) {
  return ["#2563eb", "#0284c7", "#1d4ed8", "#4f46e5", "#0ea5e9", "#64748b"][index % 6];
}
