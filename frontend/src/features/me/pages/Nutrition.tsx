"use client";

import { useRouter } from "next/navigation";
import { ChevronRight, Plus } from "lucide-react";
import { useState } from "react";
import { StatusBadge } from "@/src/components/ui/badge";
import { Button } from "@/src/components/ui/button";
import { DataTable, type Column } from "@/src/components/ui/data-table";
import { Pagination } from "@/src/components/ui/pagination";
import { ErrorState, LoadingState } from "@/src/components/ui/states";
import { usePagedApi } from "@/src/hooks/use-paged-api";
import { formatDate, formatNumber } from "@/src/lib/format";
import { PLAT_FIELDS } from "@/src/lib/payload";
import type { Plat } from "@/src/types/domain";
import { AddEntryModal, Page } from "./_shared";

export function NutritionPlatsPage() {
  const router = useRouter();
  const [adding, setAdding] = useState(false);
  const query = usePagedApi<Plat>("/api/me/plats", {}, 12);
  const rows = query.data?.data || [];
  const columns: Column<Plat>[] = [
    {
      key: "nom",
      header: "Plat",
      render: (row) => row.nom_plat || `Plat #${row.plat_id}`
    },
    { key: "repas", header: "Repas", render: (row) => row.type_repas || "N/A" },
    { key: "consomme", header: "Consomme le", render: (row) => formatDate(row.consomme_le) },
    { key: "kcal", header: "Calories totales", render: (row) => formatNumber(row.calories_totales_kcal, " kcal"), align: "right" },
    { key: "lignes", header: "Somme lignes", render: (row) => formatNumber(row.somme_lignes_kcal, " kcal"), align: "right" },
    {
      key: "coherence",
      header: "Coherence",
      render: (row) => <StatusBadge value={row.coherence_calories === false ? "INCOHERENT" : "OK"} />
    },
    {
      key: "voir",
      header: "",
      align: "right",
      render: () => <span className="row-open-hint">Voir detail <ChevronRight size={14} /></span>
    }
  ];

  return (
    <>
      <Page
        title="Plats"
        eyebrow="Nutrition"
        actions={<Button onClick={() => setAdding(true)}><Plus size={16} /> Nouveau plat</Button>}
      >
        {query.isLoading ? <LoadingState /> : null}
        {query.isError ? <ErrorState message={query.error.message} onRetry={() => query.refetch()} /> : null}
        {!query.isLoading && !query.isError ? (
          <>
            <DataTable
              rows={rows}
              columns={columns}
              getRowKey={(row) => row.plat_id}
              onRowClick={(row) => router.push(`/me/nutrition/plats/${row.plat_id}`)}
            />
            <Pagination meta={query.data?.meta} page={query.page} onPageChange={query.setPage} />
          </>
        ) : null}
      </Page>
      <AddEntryModal
        open={adding}
        onClose={() => setAdding(false)}
        title="Nouveau plat"
        path="/api/me/plats"
        invalidateKey="/api/me/plats"
        cleanOptions={PLAT_FIELDS}
        initialValues={{ consomme_le: new Date().toISOString().slice(0, 16) }}
        fields={[
          { name: "consomme_le", label: "Date", type: "datetime-local", required: true },
          { name: "type_repas", label: "Type de repas", options: [
            { label: "Petit-dejeuner", value: "PetitDejeuner" },
            { label: "Dejeuner", value: "Dejeuner" },
            { label: "Diner", value: "Diner" },
            { label: "Collation", value: "Collation" }
          ] },
          { name: "nom_plat", label: "Nom du plat" },
          { name: "calories_totales_kcal", label: "Calories (optionnel)", type: "number", step: "0.1", placeholder: "Recalculees depuis les lignes si besoin" }
        ]}
      />
    </>
  );
}
