"use client";

import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Heart, Plus } from "lucide-react";
import { Button } from "@/src/components/ui/button";
import { BarSeries } from "@/src/components/charts/BarSeries";
import { LineSeries } from "@/src/components/charts/LineSeries";
import { DateRangeFilter } from "@/src/components/filters/DateRangeFilter";
import { ChartCard, MetricCard } from "@/src/components/ui/cards";
import type { Column } from "@/src/components/ui/data-table";
import { useDateRange } from "@/src/hooks/use-date-range";
import { usePagedApi } from "@/src/hooks/use-paged-api";
import { apiRequest } from "@/src/lib/api";
import { MESURE_SOMMEIL_FIELDS } from "@/src/lib/payload";
import { compactDate, formatDate, formatNumber } from "@/src/lib/format";
import type { SommeilSante } from "@/src/types/domain";
import { AddEntryModal, ListPage } from "./_shared";

type SommeilLatest = SommeilSante & {
  tension_systolique?: number | null;
  tension_diastolique?: number | null;
};

export function SommeilPage() {
  const { range, setRange } = useDateRange();
  const [adding, setAdding] = useState(false);
  const query = usePagedApi<SommeilSante>("/api/me/sommeil-sante");
  const latest = useQuery({
    queryKey: ["/api/me/sommeil-sante/latest"],
    queryFn: () =>
      apiRequest<SommeilLatest>("/api/me/sommeil-sante/latest")
        .catch(() => null),
    retry: false
  });

  const allRows = query.data?.data || [];
  const rows = useMemo(
    () =>
      allRows.filter((row) => {
        if (!row.mesure_le) return true;
        const ts = row.mesure_le.slice(0, 10);
        if (range.from && ts < range.from) return false;
        if (range.to && ts > range.to) return false;
        return true;
      }),
    [allRows, range]
  );

  const columns: Column<SommeilSante>[] = [
    { key: "date", header: "Date", render: (row) => formatDate(row.mesure_le) },
    { key: "duree", header: "Duree", render: (row) => formatNumber(row.duree_sommeil_h, " h"), align: "right" },
    { key: "qualite", header: "Qualite", render: (row) => formatNumber(row.qualite_sommeil_score), align: "right" },
    { key: "stress", header: "Stress", render: (row) => formatNumber(row.stress_score), align: "right" },
    { key: "pas", header: "Pas", render: (row) => formatNumber(row.pas_jour), align: "right" },
    { key: "trouble", header: "Trouble", render: (row) => row.trouble_sommeil_normalise || "N/A" }
  ];
  const data = rows.slice().reverse().map((row) => ({ ...row, label: compactDate(row.mesure_le) }));

  const tension = latest.data
    ? `${latest.data.tension_systolique ?? "?"} / ${latest.data.tension_diastolique ?? "?"}`
    : "Aucune mesure";

  const summary = (
    <div className="metric-grid metric-grid-sleep">
      <MetricCard
        label="Tension (mmHg)"
        value={tension}
        icon={Heart}
      />
      <MetricCard label="Sommeil dernier" value={formatNumber(latest.data?.duree_sommeil_h, " h")} icon={Heart} />
      <MetricCard label="Stress dernier" value={formatNumber(latest.data?.stress_score)} icon={Heart} />
    </div>
  );

  const chart = (
    <div className="chart-grid">
      <ChartCard title="Sommeil & qualite" expandable data={data}>
        <LineSeries
          data={data}
          xKey="label"
          series={[
            { key: "duree_sommeil_h", label: "Sommeil (h)", color: "#7c3aed" },
            { key: "qualite_sommeil_score", label: "Qualite", color: "#0284c7" }
          ]}
        />
      </ChartCard>
      <ChartCard title="Stress" expandable data={data}>
        <LineSeries
          data={data}
          xKey="label"
          series={[{ key: "stress_score", label: "Stress", color: "#dc2626" }]}
        />
      </ChartCard>
      <ChartCard title="Pas par jour" expandable data={data}>
        <BarSeries
          data={data}
          xKey="label"
          series={[{ key: "pas_jour", label: "Pas", color: "#2563eb" }]}
        />
      </ChartCard>
      <ChartCard title="Activite physique (min/jour)" expandable data={data}>
        <BarSeries
          data={data}
          xKey="label"
          series={[{ key: "activite_physique_min_jour", label: "Activite (min)", color: "#0284c7" }]}
        />
      </ChartCard>
    </div>
  );

  return (
    <>
      <ListPage
        title="Sommeil et sante"
        eyebrow="Recuperation"
        query={query}
        rows={rows}
        columns={columns}
        getRowKey={(row) => row.mesure_sommeil_id}
        filterBar={<DateRangeFilter value={range} onChange={setRange} />}
        iconSummary={summary}
        chart={chart}
        actions={<Button onClick={() => setAdding(true)}><Plus size={16} /> Nouvelle mesure</Button>}
      />
      <AddEntryModal
        open={adding}
        onClose={() => setAdding(false)}
        title="Nouvelle mesure de sommeil"
        path="/api/me/sommeil-sante"
        invalidateKey="/api/me/sommeil-sante"
        cleanOptions={MESURE_SOMMEIL_FIELDS}
        initialValues={{ mesure_le: new Date().toISOString().slice(0, 16) }}
        fields={[
          { name: "mesure_le", label: "Date", type: "datetime-local", required: true },
          { name: "duree_sommeil_h", label: "Duree (h)", type: "number", step: "0.1" },
          { name: "qualite_sommeil_score", label: "Qualite (score)", type: "number" },
          { name: "stress_score", label: "Stress (score)", type: "number" },
          { name: "frequence_cardiaque_bpm", label: "BPM", type: "number" },
          { name: "tension_systolique", label: "Tension systolique", type: "number" },
          { name: "tension_diastolique", label: "Tension diastolique", type: "number" },
          { name: "pas_jour", label: "Pas / jour", type: "number" },
          { name: "activite_physique_min_jour", label: "Activite (min)", type: "number" },
          { name: "trouble_sommeil_normalise", label: "Trouble" }
        ]}
      />
    </>
  );
}
