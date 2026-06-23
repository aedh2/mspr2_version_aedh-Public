"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { StatusBadge } from "@/src/components/ui/badge";
import { ChartCard, MetricCard } from "@/src/components/ui/cards";
import { DataTable, type Column } from "@/src/components/ui/data-table";
import { ErrorState, LoadingState } from "@/src/components/ui/states";
import { apiRequest } from "@/src/lib/api";
import { formatDate, formatNumber } from "@/src/lib/format";
import type { ExecutionEtl, LotDonnees } from "@/src/types/domain";

type ExecutionDetail = ExecutionEtl & {
  source?: { source_id: number; nom: string; type_source?: string | null } | null;
  lots: LotDonnees[];
};

export function EtlExecutionDetailPage({ id }: { id: string }) {
  const query = useQuery({
    enabled: Boolean(id),
    queryKey: ["/api/admin/etl/executions", id],
    queryFn: () => apiRequest<ExecutionDetail>(`/api/admin/etl/executions/${id}`)
  });

  if (query.isLoading) return <LoadingState label="Chargement de l'execution..." />;
  if (query.isError) return <ErrorState message={query.error.message} onRetry={() => query.refetch()} />;
  const data = query.data!;

  const columns: Column<LotDonnees>[] = [
    {
      key: "id",
      header: "Lot",
      render: (row) => (
        <Link className="row-link" href={`/admin/etl/lots/${row.lot_id}`}>
          #{row.lot_id} {row.nom_lot ? `· ${row.nom_lot}` : ""}
        </Link>
      )
    },
    { key: "statut", header: "Statut", render: (row) => <StatusBadge value={row.statut} /> },
    { key: "cree", header: "Cree le", render: (row) => formatDate(row.cree_le) },
    { key: "valide", header: "Valide le", render: (row) => formatDate(row.valide_le) }
  ];

  return (
    <section className="page-section">
      <Link href="/admin/etl/executions" className="back-link">
        <ArrowLeft size={14} /> Retour aux executions
      </Link>
      <header className="detail-hero">
        <span className="eyebrow">Execution · #{data.execution_id}</span>
        <h1><em>{data.source?.nom || `Source #${data.source_id ?? "?"}`}</em></h1>
        <div className="hero-meta">
          <div className="kv"><span>Statut</span><strong><StatusBadge value={data.statut} /></strong></div>
          <div className="kv"><span>Demarree</span><strong>{formatDate(data.demarre_le)}</strong></div>
          <div className="kv"><span>Terminee</span><strong>{formatDate(data.termine_le)}</strong></div>
          <div className="kv"><span>Qualite</span><strong>{formatNumber(data.taux_qualite, " %")}</strong></div>
        </div>
      </header>

      <div className="metric-grid">
        <MetricCard label="Lignes lues" value={formatNumber(data.lignes_lues)} />
        <MetricCard label="Valides" value={formatNumber(data.lignes_valides)} />
        <MetricCard label="Invalides" value={formatNumber(data.lignes_invalides)} />
        <MetricCard label="Rejets" value={formatNumber(data.nb_rejets)} />
      </div>

      {data.message ? (
        <div className="callout"><strong>Message :</strong> {data.message}</div>
      ) : null}

      <ChartCard title={`Lots associes (${data.lots.length})`}>
        <DataTable rows={data.lots} columns={columns} getRowKey={(row) => row.lot_id} emptyLabel="Aucun lot rattache." />
      </ChartCard>
    </section>
  );
}
