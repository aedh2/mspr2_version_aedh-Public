"use client";

import { useMemo, useState } from "react";
import { Plus } from "lucide-react";
import { LineSeries } from "@/src/components/charts/LineSeries";
import { DateRangeFilter } from "@/src/components/filters/DateRangeFilter";
import { Button } from "@/src/components/ui/button";
import { ChartCard } from "@/src/components/ui/cards";
import type { Column } from "@/src/components/ui/data-table";
import { useDateRange } from "@/src/hooks/use-date-range";
import { usePagedApi } from "@/src/hooks/use-paged-api";
import { compactDate, formatDate, formatNumber } from "@/src/lib/format";
import { MESURE_BIOMETRIQUE_FIELDS } from "@/src/lib/payload";
import type { MesureBiometrique } from "@/src/types/domain";
import { AddEntryModal, ListPage } from "./_shared";

export function BiometriePage() {
  const { range, setRange } = useDateRange();
  const [adding, setAdding] = useState(false);
  const query = usePagedApi<MesureBiometrique>("/api/me/mesures-biometriques");
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
  const columns: Column<MesureBiometrique>[] = [
    { key: "date", header: "Date", render: (row) => formatDate(row.mesure_le) },
    { key: "poids", header: "Poids", render: (row) => formatNumber(row.poids_kg, " kg"), align: "right" },
    { key: "imc", header: "IMC", render: (row) => formatNumber(row.imc), align: "right" },
    { key: "masse", header: "Masse grasse", render: (row) => formatNumber(row.taux_masse_grasse, " %"), align: "right" },
    { key: "bpm", header: "BPM moyen", render: (row) => formatNumber(row.bpm_moyen), align: "right" },
    { key: "eau", header: "Eau", render: (row) => formatNumber(row.eau_l, " L"), align: "right" }
  ];
  const trend = rows.slice().reverse().map((row) => ({ ...row, label: compactDate(row.mesure_le) }));
  const chart = (
    <div className="chart-grid">
      <ChartCard title="Tendance poids / IMC" expandable data={trend}>
        <LineSeries
          data={trend}
          xKey="label"
          series={[
            { key: "poids_kg", label: "Poids", color: "#2563eb" },
            { key: "imc", label: "IMC", color: "#0284c7" }
          ]}
        />
      </ChartCard>
      <ChartCard title="Masse grasse & hydratation" expandable data={trend}>
        <LineSeries
          data={trend}
          xKey="label"
          series={[
            { key: "taux_masse_grasse", label: "Masse grasse %", color: "#b54708" },
            { key: "eau_l", label: "Eau (L)", color: "#7c3aed" }
          ]}
        />
      </ChartCard>
      <ChartCard title="Frequence cardiaque" expandable data={trend}>
        <LineSeries
          data={trend}
          xKey="label"
          series={[
            { key: "bpm_repos", label: "Repos", color: "#0284c7" },
            { key: "bpm_moyen", label: "Moyen", color: "#2563eb" },
            { key: "bpm_max", label: "Max", color: "#dc2626" }
          ]}
        />
      </ChartCard>
    </div>
  );
  return (
    <>
      <ListPage
        title="Mesures biometriques"
        eyebrow="Sante"
        query={query}
        rows={rows}
        columns={columns}
        getRowKey={(row) => row.mesure_id}
        filterBar={<DateRangeFilter value={range} onChange={setRange} />}
        chart={chart}
        actions={<Button onClick={() => setAdding(true)}><Plus size={16} /> Nouvelle mesure</Button>}
      />
      <AddEntryModal
        open={adding}
        onClose={() => setAdding(false)}
        title="Nouvelle mesure biometrique"
        path="/api/me/mesures-biometriques"
        invalidateKey="/api/me/mesures-biometriques"
        cleanOptions={MESURE_BIOMETRIQUE_FIELDS}
        initialValues={{ mesure_le: new Date().toISOString().slice(0, 16) }}
        fields={[
          { name: "mesure_le", label: "Date", type: "datetime-local", required: true },
          { name: "poids_kg", label: "Poids (kg)", type: "number", step: "0.1" },
          { name: "taille_cm", label: "Taille (cm)", type: "number", step: "0.1" },
          { name: "imc", label: "IMC (optionnel)", type: "number", step: "0.01", placeholder: "Calcule automatiquement si possible" },
          { name: "taux_masse_grasse", label: "Masse grasse (%)", type: "number", step: "0.1" },
          { name: "bpm_repos", label: "BPM repos", type: "number" },
          { name: "bpm_moyen", label: "BPM moyen", type: "number" },
          { name: "bpm_max", label: "BPM max", type: "number" },
          { name: "eau_l", label: "Eau (L)", type: "number", step: "0.1" }
        ]}
      />
    </>
  );
}
