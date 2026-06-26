import { AlertTriangle, CheckCircle2, ShieldCheck, Sparkles } from "lucide-react";
import { HealthProgress } from "@/src/components/health/health-widgets";
import { formatNumber } from "@/src/lib/format";

export type RecommendationMetric = {
  label: string;
  value?: number | null;
  suffix?: string;
};

export type RecommendationDetail = {
  label: string;
  value?: string | number | null;
};

export function RecommendationCard({
  eyebrow,
  title,
  description,
  justification,
  score,
  safetyScore,
  confidenceScore,
  metrics = [],
  details = [],
  badges = [],
  alternatives = [],
  warning
}: {
  eyebrow: string;
  title: string;
  description: string;
  justification?: string | null;
  score?: number | null;
  safetyScore?: number | null;
  confidenceScore?: number | null;
  metrics?: RecommendationMetric[];
  details?: RecommendationDetail[];
  badges?: string[];
  alternatives?: string[];
  warning?: string | null;
}) {
  const visibleDetails = details.filter((detail) => detail.value !== null && detail.value !== undefined && String(detail.value).trim());

  return (
    <article className="recommendation-card recommendation-card-premium">
      <div className="recommendation-card-head">
        <div>
          <p className="eyebrow">{eyebrow}</p>
          <h3>{title}</h3>
        </div>
        <span className="recommendation-score-badge">
          {score === null || score === undefined ? "N/A" : `${score}/100`}
        </span>
      </div>
      <p>{description}</p>
      {metrics.length ? (
        <div className="recommendation-macro-grid">
          {metrics.map((metric) => (
            <span key={metric.label}>
              <strong>{formatNumber(metric.value, metric.suffix || "")}</strong>
              {metric.label}
            </span>
          ))}
        </div>
      ) : null}
      {visibleDetails.length ? (
        <dl className="recommendation-detail-list">
          {visibleDetails.map((detail) => (
            <div key={detail.label}>
              <dt>{detail.label}</dt>
              <dd>{detail.value}</dd>
            </div>
          ))}
        </dl>
      ) : null}
      <div className="recommendation-score-stack">
        <HealthProgress label="Pertinence" value={score} tone="teal" />
        <HealthProgress label="Securite" value={safetyScore} tone="green" />
        <HealthProgress label="Confiance" value={confidenceScore ?? score} tone="blue" />
      </div>
      <BadgeList items={badges} />
      {justification ? (
        <div className="recommendation-justification">
          <strong>Pourquoi ce plat ?</strong>
          <span>{justification}</span>
        </div>
      ) : null}
      {alternatives.length ? (
        <div className="recommendation-alt">
          <Sparkles size={15} aria-hidden />
          <span>Alternatives: {alternatives.join(", ")}</span>
        </div>
      ) : null}
      {warning ? (
        <div className="recommendations-warning" role="note">
          <AlertTriangle size={16} />
          <span>{warning}</span>
        </div>
      ) : null}
    </article>
  );
}

export function ConstraintBadgeList({ items }: { items: string[] }) {
  const unique = Array.from(new Set(items.filter(Boolean)));
  if (!unique.length) return null;
  return (
    <div className="constraint-badge-list">
      {unique.map((item) => (
        <span className="badge badge-success" key={item}>
          <CheckCircle2 size={13} aria-hidden />
          {item}
        </span>
      ))}
    </div>
  );
}

function BadgeList({ items }: { items: string[] }) {
  const unique = Array.from(new Set(items.filter(Boolean))).slice(0, 10);
  if (!unique.length) return null;
  return (
    <div className="badge-row">
      {unique.map((item) => (
        <span className="badge badge-neutral" key={item}>
          <ShieldCheck size={13} aria-hidden />
          {item}
        </span>
      ))}
    </div>
  );
}
