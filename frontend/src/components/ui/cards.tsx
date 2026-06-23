"use client";

import type { LucideIcon } from "lucide-react";
import { Expand, Info } from "lucide-react";
import { useState } from "react";
import { Button } from "@/src/components/ui/button";
import { Modal } from "@/src/components/ui/modal";

export function MetricCard({
  label,
  value,
  hint,
  icon: Icon
}: {
  label: string;
  value: React.ReactNode;
  hint?: string;
  icon?: LucideIcon;
}) {
  return (
    <article className="metric-card">
      <div>
        <p>{label}</p>
        <strong>{value ?? "N/A"}</strong>
        {hint ? <span>{hint}</span> : null}
      </div>
      {Icon ? <Icon size={20} /> : null}
    </article>
  );
}

type ChartCardProps = {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  data?: Record<string, unknown>[] | null;
  expandable?: boolean;
  empty?: boolean;
  emptyLabel?: string;
  modalTitle?: string;
};

export function ChartCard({
  title,
  subtitle,
  children,
  data,
  expandable = false,
  empty = false,
  emptyLabel,
  modalTitle
}: ChartCardProps) {
  const [open, setOpen] = useState(false);
  const clickable = expandable && !empty;

  return (
    <>
      <section
        className={`chart-card${clickable ? " chart-card-expandable" : ""}`}
        role={clickable ? "button" : undefined}
        tabIndex={clickable ? 0 : undefined}
        onClick={clickable ? () => setOpen(true) : undefined}
        onKeyDown={clickable ? (event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            setOpen(true);
          }
        } : undefined}
      >
        <div className="chart-card-header">
          <div>
            <h2>{title}</h2>
            {subtitle ? <p>{subtitle}</p> : null}
          </div>
          {clickable ? (
            <button
              type="button"
              className="chart-card-action"
              onClick={(event) => {
                event.stopPropagation();
                setOpen(true);
              }}
            >
              <Expand size={16} />
              Agrandir
            </button>
          ) : null}
        </div>
        <div className="chart-body">
          {empty ? <div className="empty-chart">{emptyLabel || "Aucune donnee."}</div> : children}
        </div>
      </section>

      {clickable ? (
        <Modal title={modalTitle || title} open={open} onClose={() => setOpen(false)} className="chart-modal">
          <div className="chart-detail-stack">
            <div className="chart-detail-body">{children}</div>
            {data?.length ? (
              <div className="table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      {Object.keys(data[0]).map((key) => <th key={key}>{key}</th>)}
                    </tr>
                  </thead>
                  <tbody>
                    {data.map((row, index) => (
                      <tr key={index}>
                        {Object.keys(data[0]).map((key) => (
                          <td key={key} data-label={key}>{formatCell(row[key])}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="empty-inline">
                <Info size={16} />
                Aucun tableau detaille disponible.
              </div>
            )}
          </div>
        </Modal>
      ) : null}
    </>
  );
}

function formatCell(value: unknown) {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "object") return "Donnee structuree";
  return String(value);
}
