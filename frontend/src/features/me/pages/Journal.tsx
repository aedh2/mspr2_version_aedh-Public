"use client";

import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { BarSeries } from "@/src/components/charts/BarSeries";
import { PieSeries } from "@/src/components/charts/PieSeries";
import { ChartCard } from "@/src/components/ui/cards";
import type { Column } from "@/src/components/ui/data-table";
import { useNutritionCharts } from "@/src/features/nutrition/hooks";
import { usePagedApi } from "@/src/hooks/use-paged-api";
import { compactDate, formatDate, formatNumber } from "@/src/lib/format";
import type { JournalAlimentaire } from "@/src/types/domain";
import { ListPage } from "./_shared";

export function JournalPage() {
  const query = usePagedApi<JournalAlimentaire>("/api/me/journal-alimentaire");
  const charts = useNutritionCharts("day");
  const rows = query.data?.data || [];
  const columns: Column<JournalAlimentaire>[] = [
    { key: "date", header: "Date", render: (row) => formatDate(row.consomme_le) },
    { key: "repas", header: "Repas", render: (row) => row.type_repas || "N/A" },
    {
      key: "aliment",
      header: "Aliment / plat",
      render: (row) =>
        row.plat_id ? (
          <Link className="row-open-hint" href={`/me/nutrition/plats/${row.plat_id}`}>
            {row.aliment_nom_libre || `Plat #${row.plat_id}`} <ChevronRight size={14} />
          </Link>
        ) : (
          row.aliment_nom_libre || `Ref #${row.aliment_id || "N/A"}`
        )
    },
    { key: "quantite", header: "Quantite", render: (row) => `${formatNumber(row.quantite)} ${row.unite_quantite || ""}`.trim(), align: "right" },
    { key: "calories", header: "Calories", render: (row) => formatNumber(row.calories_kcal, " kcal"), align: "right" },
    { key: "eau", header: "Eau", render: (row) => formatNumber(row.eau_ml, " ml"), align: "right" }
  ];

  const caloriesData = (charts.data?.calories_par_bucket || []).map((row) => ({
    ...row,
    label: compactDate(row.bucket)
  }));
  const repartition = charts.data?.repartition_repas || [];
  const topAliments = charts.data?.top_aliments || [];

  const chart = (
    <div className="chart-grid">
      <ChartCard title="Calories par jour" expandable data={caloriesData}>
        <BarSeries data={caloriesData} xKey="label" series={[{ key: "calories", label: "Calories", color: "#0284c7" }]} />
      </ChartCard>
      <ChartCard title="Repartition par repas" expandable data={repartition as Record<string, unknown>[]}>
        <PieSeries data={repartition} dataKey="nb" nameKey="type_repas" />
      </ChartCard>
    </div>
  );

  const topList =
    topAliments.length > 0 ? (
      <section className="chart-card">
        <h2>Top aliments</h2>
        <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: 8 }}>
          {topAliments.slice(0, 6).map((a) => (
            <li
              key={a.aliment_id}
              style={{
                display: "flex",
                justifyContent: "space-between",
                gap: 12,
                paddingBottom: 8,
                borderBottom: "1px solid var(--rule)"
              }}
            >
              <span style={{ fontFamily: "var(--font-display)", fontWeight: 500 }}>{a.nom}</span>
              <span className="tabular muted">
                {a.nb}× · {formatNumber(a.calories, " kcal")}
              </span>
            </li>
          ))}
        </ul>
      </section>
    ) : null;

  return (
    <ListPage
      title="Journal alimentaire"
      eyebrow="Nutrition"
      query={query}
      rows={rows}
      columns={columns}
      getRowKey={(row) => row.journal_id}
      chart={
        <>
          {chart}
          {topList}
        </>
      }
    />
  );
}
