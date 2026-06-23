"use client";

import { useQuery } from "@tanstack/react-query";
import { DatabaseZap, ShieldAlert, Users } from "lucide-react";
import { BarSeries } from "@/src/components/charts/BarSeries";
import { LineSeries } from "@/src/components/charts/LineSeries";
import { PieSeries } from "@/src/components/charts/PieSeries";
import { ChartCard, MetricCard } from "@/src/components/ui/cards";
import { ErrorState, LoadingState } from "@/src/components/ui/states";
import { apiRequest } from "@/src/lib/api";
import { compactDate, formatNumber } from "@/src/lib/format";
import type { AdminDashboard } from "@/src/types/domain";
import { Page } from "./_shared";

type QualityBySource = { source_id: number; nom: string; qualite_moy: number | null; nb_executions: number };
type RejectsByLot = { lot_id: number; nom_lot: string; nb_rejets: number; nb_anomalies?: number; value: number };
type ImportsVolume = { bucket: string; lignes_lues: number; lignes_valides: number; lignes_invalides: number; nb_rejets: number };
type UsersByOrg = { organisation_id: number; nom: string; nb_users: number };
type TopRule = { regle_id: number; code_regle: string; severite: string; nb: number };

function useChart<T>(path: string) {
  return useQuery({ queryKey: [path], queryFn: () => apiRequest<T>(path) });
}

export function AdminDashboardPage() {
  const dashboard = useQuery({ queryKey: ["admin-dashboard"], queryFn: () => apiRequest<AdminDashboard>("/api/admin/dashboard") });
  const qualityBySource = useChart<QualityBySource[]>("/api/admin/dashboard/charts/quality-by-source");
  const rejectsByLot = useChart<RejectsByLot[]>("/api/admin/dashboard/charts/rejects-by-lot");
  const importsVolume = useChart<ImportsVolume[]>("/api/admin/dashboard/charts/imports-volume");
  const usersByOrg = useChart<UsersByOrg[]>("/api/admin/dashboard/charts/users-by-organisation");
  const topRules = useChart<TopRule[]>("/api/admin/dashboard/charts/top-rules");

  if (dashboard.isLoading) return <LoadingState />;
  if (dashboard.isError) return <ErrorState message={dashboard.error.message} onRetry={() => dashboard.refetch()} />;
  const data = dashboard.data;

  const importsData = (importsVolume.data || []).map((row) => ({ ...row, label: compactDate(row.bucket) }));
  const rejectsData = (rejectsByLot.data || []).map((row) => ({
    ...row,
    label: row.nb_rejets > 0 ? "Rejets" : "Anomalies"
  }));

  return (
    <Page title="Dashboard admin" eyebrow="Pilotage" subtitle="Suivi des utilisateurs, imports ETL et controles qualite.">
      <div className="metric-grid">
        <MetricCard label="Utilisateurs" value={data?.nb_utilisateurs ?? 0} icon={Users} />
        <MetricCard label="Aliments" value={data?.nb_aliments ?? 0} icon={DatabaseZap} />
        <MetricCard label="Executions ETL" value={data?.nb_executions_etl ?? 0} icon={DatabaseZap} />
        <MetricCard label="Qualite moyenne" value={formatNumber(data?.taux_qualite_moyen, " %")} icon={ShieldAlert} />
        <MetricCard label="Controles bloquants" value={data?.controles_bloquants ?? 0} icon={ShieldAlert} />
      </div>

      <div className="chart-grid">
        <ChartCard title="Qualite par source" expandable data={qualityBySource.data || []} empty={!qualityBySource.data?.length}>
          <BarSeries
            data={(qualityBySource.data || []).map((row) => ({ ...row, qualite: row.qualite_moy ?? 0 }))}
            xKey="nom"
            series={[{ key: "qualite", label: "Qualite moyenne (%)", color: "#0284c7" }]}
          />
        </ChartCard>
        <ChartCard title="Top lots avec rejets" subtitle="Basculera en anomalies si aucun rejet n'est present" expandable data={rejectsData} empty={!rejectsData.length}>
          <BarSeries
            data={rejectsData}
            xKey="nom_lot"
            series={[{ key: "value", label: "Volume", color: "#dc2626" }]}
          />
        </ChartCard>
      </div>

      <div className="chart-grid">
        <ChartCard title="Volume d'imports (90j)" expandable data={importsData} empty={!importsData.length}>
          <LineSeries
            data={importsData}
            xKey="label"
            series={[
              { key: "lignes_lues", label: "Lues", color: "#2563eb" },
              { key: "lignes_valides", label: "Valides", color: "#0284c7" },
              { key: "lignes_invalides", label: "Invalides", color: "#b54708" },
              { key: "nb_rejets", label: "Rejets", color: "#dc2626" }
            ]}
          />
        </ChartCard>
        <ChartCard title="Utilisateurs par organisation" expandable data={usersByOrg.data || []} empty={!usersByOrg.data?.length}>
          <PieSeries data={usersByOrg.data || []} dataKey="nb_users" nameKey="nom" />
        </ChartCard>
      </div>

      <ChartCard title="Top regles declenchees" expandable data={topRules.data || []} empty={!topRules.data?.length}>
        <BarSeries data={topRules.data || []} xKey="code_regle" series={[{ key: "nb", label: "Occurrences", color: "#2563eb" }]} />
      </ChartCard>
    </Page>
  );
}
