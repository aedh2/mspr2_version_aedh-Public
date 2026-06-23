"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { ArrowLeft } from "lucide-react";
import { StatusBadge } from "@/src/components/ui/badge";
import { Button } from "@/src/components/ui/button";
import { ChartCard, MetricCard } from "@/src/components/ui/cards";
import { DataTable, type Column } from "@/src/components/ui/data-table";
import { Pagination } from "@/src/components/ui/pagination";
import { ErrorState, LoadingState } from "@/src/components/ui/states";
import { usePagedApi } from "@/src/hooks/use-paged-api";
import { apiRequest } from "@/src/lib/api";
import { formatDate, formatNumber } from "@/src/lib/format";
import type { ControleQualite, LotDonnees } from "@/src/types/domain";

type LotResume = LotDonnees & {
  source?: { source_id: number; nom: string; type_source?: string | null } | null;
  execution?: { execution_id: number; statut: string; taux_qualite?: number | null } | null;
  compteurs: { raw: number; staging: number; controles: number; controles_bloquants: number };
};

type RawRow = {
  enregistrement_id: number;
  entite: string;
  ref_externe?: string | null;
  payload_json?: string | null;
  cree_le?: string | null;
};

type StgRow = {
  stg_id: number;
  entite: string;
  ref_externe?: string | null;
  source_payload_json?: string | null;
  payload_normalise_json?: string | null;
  est_parseable?: boolean | null;
  statut_validation?: string | null;
  code_rejet_potentiel?: string | null;
};

type Tab = "raw" | "staging" | "controles" | "impacts";

export function EtlLotDetailPage({ id }: { id: string }) {
  const resume = useQuery({
    enabled: Boolean(id),
    queryKey: ["/api/admin/etl/lots", id, "resume"],
    queryFn: () => apiRequest<LotResume>(`/api/admin/etl/lots/${id}/resume`)
  });
  const impacts = useQuery({
    enabled: Boolean(id),
    queryKey: ["/api/admin/etl/lots", id, "impacts"],
    queryFn: () => apiRequest<Record<string, number>>(`/api/admin/etl/lots/${id}/impacts`)
  });
  const [tab, setTab] = useState<Tab>("raw");

  if (resume.isLoading) return <LoadingState label="Chargement du lot..." />;
  if (resume.isError) return <ErrorState message={resume.error.message} onRetry={() => resume.refetch()} />;
  const data = resume.data!;

  return (
    <section className="page-section">
      <Link href="/admin/etl/lots" className="back-link">
        <ArrowLeft size={14} /> Retour aux lots
      </Link>
      <header className="detail-hero">
        <span className="eyebrow">Lot · #{data.lot_id}</span>
        <h1><em>{data.nom_lot || `Lot #${data.lot_id}`}</em></h1>
        <div className="hero-meta">
          <div className="kv"><span>Statut</span><strong><StatusBadge value={data.statut} /></strong></div>
          <div className="kv"><span>Source</span><strong>{data.source?.nom || `#${data.source_id ?? "?"}`}</strong></div>
          <div className="kv"><span>Execution</span>
            <strong>
              {data.execution_id ? (
                <Link href={`/admin/etl/executions/${data.execution_id}`} className="row-link">
                  #{data.execution_id}
                </Link>
              ) : "—"}
            </strong>
          </div>
          <div className="kv"><span>Cree le</span><strong>{formatDate(data.cree_le)}</strong></div>
        </div>
      </header>

      <div className="metric-grid">
        <MetricCard label="Lignes brutes" value={formatNumber(data.compteurs.raw)} />
        <MetricCard label="Lignes staging" value={formatNumber(data.compteurs.staging)} />
        <MetricCard label="Controles" value={formatNumber(data.compteurs.controles)} />
        <MetricCard label="Bloquants" value={formatNumber(data.compteurs.controles_bloquants)} />
      </div>

      {data.commentaire_validation ? (
        <div className="callout"><strong>Commentaire validation :</strong> {data.commentaire_validation}</div>
      ) : null}

      <div className="tab-bar">
        {(["raw", "staging", "controles", "impacts"] as Tab[]).map((key) => (
          <Button key={key} variant={tab === key ? "primary" : "secondary"} onClick={() => setTab(key)} type="button">
            {key === "raw" ? "Donnees brutes" : key === "staging" ? "Staging" : key === "controles" ? "Controles" : "Impacts"}
          </Button>
        ))}
      </div>

      {tab === "raw" ? <RawTable lotId={id} /> : null}
      {tab === "staging" ? <StagingTable lotId={id} /> : null}
      {tab === "controles" ? <ControlesTable lotId={id} /> : null}
      {tab === "impacts" ? <ImpactsCards impacts={impacts.data} /> : null}
    </section>
  );
}

function RawTable({ lotId }: { lotId: string }) {
  const query = usePagedApi<RawRow>(`/api/admin/etl/lots/${lotId}/raw`);
  const rows = query.data?.data || [];
  const columns: Column<RawRow>[] = [
    { key: "id", header: "ID", render: (row) => row.enregistrement_id, align: "right" },
    { key: "entite", header: "Entite", render: (row) => row.entite },
    { key: "ref", header: "Ref externe", render: (row) => row.ref_externe || "—" },
    {
      key: "payload",
      header: "Payload",
      render: (row) => (
        <code style={{ fontSize: 11, whiteSpace: "pre-wrap", wordBreak: "break-all" }}>
          {(row.payload_json || "").slice(0, 160)}
          {(row.payload_json?.length || 0) > 160 ? "…" : ""}
        </code>
      )
    },
    { key: "cree", header: "Cree le", render: (row) => formatDate(row.cree_le) }
  ];
  return (
    <ChartCard title="Donnees brutes">
      {query.isLoading ? <LoadingState /> : null}
      {query.isError ? <ErrorState message={query.error.message} onRetry={() => query.refetch()} /> : null}
      {!query.isLoading && !query.isError ? (
        <>
          <DataTable rows={rows} columns={columns} getRowKey={(row) => row.enregistrement_id} />
          <Pagination meta={query.data?.meta} page={query.page} onPageChange={query.setPage} />
        </>
      ) : null}
    </ChartCard>
  );
}

function StagingTable({ lotId }: { lotId: string }) {
  const query = usePagedApi<StgRow>(`/api/admin/etl/lots/${lotId}/staging`);
  const rows = query.data?.data || [];
  const columns: Column<StgRow>[] = [
    { key: "id", header: "ID", render: (row) => row.stg_id, align: "right" },
    { key: "entite", header: "Entite", render: (row) => row.entite },
    { key: "ref", header: "Ref externe", render: (row) => row.ref_externe || "—" },
    { key: "parse", header: "Parse", render: (row) => <StatusBadge value={row.est_parseable === false ? "KO" : "OK"} /> },
    { key: "valid", header: "Validation", render: (row) => row.statut_validation || "—" },
    { key: "rejet", header: "Code rejet", render: (row) => row.code_rejet_potentiel || "—" }
  ];
  return (
    <ChartCard title="Staging normalise">
      {query.isLoading ? <LoadingState /> : null}
      {query.isError ? <ErrorState message={query.error.message} onRetry={() => query.refetch()} /> : null}
      {!query.isLoading && !query.isError ? (
        <>
          <DataTable rows={rows} columns={columns} getRowKey={(row) => row.stg_id} />
          <Pagination meta={query.data?.meta} page={query.page} onPageChange={query.setPage} />
        </>
      ) : null}
    </ChartCard>
  );
}

function ControlesTable({ lotId }: { lotId: string }) {
  const query = usePagedApi<ControleQualite>(`/api/admin/etl/lots/${lotId}/controles`);
  const rows = query.data?.data || [];
  const columns: Column<ControleQualite>[] = [
    { key: "id", header: "ID", render: (row) => row.controle_id, align: "right" },
    { key: "entite", header: "Entite", render: (row) => row.entite },
    { key: "champ", header: "Champ", render: (row) => row.nom_champ || "—" },
    { key: "niveau", header: "Niveau", render: (row) => <StatusBadge value={row.niveau} /> },
    { key: "decision", header: "Decision", render: (row) => row.decision_finale || "—" },
    { key: "bloquant", header: "Bloquant", render: (row) => <StatusBadge value={row.est_bloquant} /> }
  ];
  return (
    <ChartCard title="Controles qualite du lot">
      {query.isLoading ? <LoadingState /> : null}
      {query.isError ? <ErrorState message={query.error.message} onRetry={() => query.refetch()} /> : null}
      {!query.isLoading && !query.isError ? (
        <>
          <DataTable rows={rows} columns={columns} getRowKey={(row) => row.controle_id} />
          <Pagination meta={query.data?.meta} page={query.page} onPageChange={query.setPage} />
        </>
      ) : null}
    </ChartCard>
  );
}

function ImpactsCards({ impacts }: { impacts?: Record<string, number> }) {
  const entries = Object.entries(impacts || {});
  if (entries.length === 0) {
    return <ChartCard title="Impacts metiers"><div className="muted">Aucun impact identifie.</div></ChartCard>;
  }
  return (
    <ChartCard title="Impacts metiers">
      <div className="metric-grid">
        {entries.map(([label, count]) => (
          <MetricCard key={label} label={label} value={formatNumber(count)} />
        ))}
      </div>
    </ChartCard>
  );
}
