"use client";

import { useMemo, useState } from "react";
import { StatusBadge } from "@/src/components/ui/badge";
import { Input, Select } from "@/src/components/ui/forms";
import type { Column } from "@/src/components/ui/data-table";
import { usePagedApi } from "@/src/hooks/use-paged-api";
import type { ControleQualite } from "@/src/types/domain";
import { CrudList, Page } from "./_shared";

export function QualityControlsPage() {
  const [niveau, setNiveau] = useState("");
  const [blocking, setBlocking] = useState("");
  const query = usePagedApi<ControleQualite>("/api/controles-qualite-donnees");
  const rows = useMemo(
    () =>
      (query.data?.data || []).filter((row) => {
        if (niveau && row.niveau !== niveau) return false;
        if (blocking && String(Boolean(row.est_bloquant)) !== blocking) return false;
        return true;
      }),
    [blocking, niveau, query.data]
  );
  const columns: Column<ControleQualite>[] = [
    { key: "id", header: "ID", render: (row) => row.controle_id, align: "right" },
    { key: "entity", header: "Entite", render: (row) => row.entite },
    { key: "field", header: "Champ", render: (row) => row.nom_champ || "N/A" },
    { key: "level", header: "Niveau", render: (row) => <StatusBadge value={row.niveau} /> },
    { key: "blocking", header: "Bloquant", render: (row) => <StatusBadge value={row.est_bloquant} /> },
    { key: "decision", header: "Decision", render: (row) => row.decision_finale || "N/A" },
    { key: "desc", header: "Description", render: (row) => row.description || row.code_controle || "N/A" }
  ];
  return (
    <Page title="Controles qualite" eyebrow="Gouvernance">
      <div className="filter-bar">
        <Input placeholder="Niveau" value={niveau} onChange={(event) => setNiveau(event.target.value)} />
        <Select value={blocking} onChange={(event) => setBlocking(event.target.value)}>
          <option value="">Bloquant: tous</option>
          <option value="true">Oui</option>
          <option value="false">Non</option>
        </Select>
      </div>
      <CrudList query={query} rows={rows} columns={columns} getRowKey={(row) => row.controle_id} />
    </Page>
  );
}
