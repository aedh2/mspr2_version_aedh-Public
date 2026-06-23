"use client";

import { ChevronRight } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { StatusBadge } from "@/src/components/ui/badge";
import type { Column } from "@/src/components/ui/data-table";
import { Select } from "@/src/components/ui/forms";
import { usePagedApi } from "@/src/hooks/use-paged-api";
import { formatDate } from "@/src/lib/format";
import type { LotDonnees } from "@/src/types/domain";
import { CrudList, Page } from "./_shared";

export function EtlLotsPage() {
  const router = useRouter();
  const [statut, setStatut] = useState("");
  const query = usePagedApi<LotDonnees>("/api/lots-donnees", statut ? { statut } : {});
  useEffect(() => {
    query.setPage(1);
  }, [statut]);
  const rows = query.data?.data || [];
  const columns: Column<LotDonnees>[] = [
    {
      key: "id",
      header: "Lot",
      render: (row) => `#${row.lot_id}`
    },
    { key: "nom", header: "Nom", render: (row) => row.nom_lot || "—" },
    { key: "exec", header: "Execution", render: (row) => row.execution_id ?? "—", align: "right" },
    { key: "source", header: "Source", render: (row) => row.source_id ?? "—", align: "right" },
    { key: "statut", header: "Statut", render: (row) => <StatusBadge value={row.statut} /> },
    { key: "cree", header: "Cree le", render: (row) => formatDate(row.cree_le) },
    { key: "valide", header: "Valide le", render: (row) => formatDate(row.valide_le) },
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
    <Page title="Lots de donnees" eyebrow="ETL">
      <div className="filter-bar">
        <Select value={statut} onChange={(event) => setStatut(event.target.value)}>
          <option value="">Tous les statuts</option>
          <option value="EN_ATTENTE">En attente</option>
          <option value="VALIDE">Valide</option>
          <option value="REJETE">Rejete</option>
          <option value="ARCHIVE">Archive</option>
        </Select>
      </div>
      <CrudList query={query} rows={rows} columns={columns} getRowKey={(row) => row.lot_id} onRowClick={(row) => router.push(`/admin/etl/lots/${row.lot_id}`)} />
    </Page>
  );
}
