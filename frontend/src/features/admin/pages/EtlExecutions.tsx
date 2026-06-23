"use client";

import { ChevronRight } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { StatusBadge } from "@/src/components/ui/badge";
import { Input } from "@/src/components/ui/forms";
import type { Column } from "@/src/components/ui/data-table";
import { usePagedApi } from "@/src/hooks/use-paged-api";
import { formatDate, formatNumber } from "@/src/lib/format";
import type { ExecutionEtl } from "@/src/types/domain";
import { CrudList, Page } from "./_shared";

export function EtlExecutionsPage() {
  const router = useRouter();
  const [statut, setStatut] = useState("");
  const query = usePagedApi<ExecutionEtl>("/api/executions-etl", statut ? { statut } : {});
  const rows = query.data?.data || [];
  useEffect(() => {
    query.setPage(1);
  }, [statut]);
  const columns: Column<ExecutionEtl>[] = [
    {
      key: "id",
      header: "ID",
      align: "right",
      render: (row) => `#${row.execution_id}`
    },
    { key: "statut", header: "Statut", render: (row) => <StatusBadge value={row.statut} /> },
    { key: "start", header: "Demarrage", render: (row) => formatDate(row.demarre_le) },
    { key: "valid", header: "Valides", render: (row) => formatNumber(row.lignes_valides), align: "right" },
    { key: "invalid", header: "Invalides", render: (row) => formatNumber(row.lignes_invalides), align: "right" },
    { key: "quality", header: "Qualite", render: (row) => formatNumber(row.taux_qualite, " %"), align: "right" },
    { key: "msg", header: "Message", render: (row) => row.message || "N/A" }
    ,
    {
      key: "open",
      header: "",
      align: "right",
      headerClassName: "row-open-cell",
      cellClassName: "row-open-cell",
      render: () => <span className="row-open-hint">Voir detail <ChevronRight size={14} /></span>
    }
  ];
  return (
    <Page title="Executions ETL" eyebrow="Audit">
      <div className="filter-bar">
        <Input placeholder="Filtrer par statut" value={statut} onChange={(event) => setStatut(event.target.value)} />
      </div>
      <CrudList query={query} rows={rows} columns={columns} getRowKey={(row) => row.execution_id} onRowClick={(row) => router.push(`/admin/etl/executions/${row.execution_id}`)} />
    </Page>
  );
}
