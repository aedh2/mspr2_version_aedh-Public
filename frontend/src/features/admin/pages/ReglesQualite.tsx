"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { StatusBadge } from "@/src/components/ui/badge";
import { Button } from "@/src/components/ui/button";
import type { Column } from "@/src/components/ui/data-table";
import { Input, Select } from "@/src/components/ui/forms";
import { useDebouncedValue } from "@/src/hooks/use-debounced-value";
import { usePagedApi } from "@/src/hooks/use-paged-api";
import { apiRequest } from "@/src/lib/api";
import { cleanPayload, REGLE_QUALITE_FIELDS } from "@/src/lib/payload";
import type { RegleQualite } from "@/src/types/domain";
import { CrudList, Page } from "./_shared";

export function ReglesQualitePage() {
  const [search, setSearch] = useState("");
  const debounced = useDebouncedValue(search, 300);
  const [severite, setSeverite] = useState("");
  const [actifFilter, setActifFilter] = useState("true");

  const params: Record<string, string> = {};
  if (debounced) params.q = debounced;
  if (severite) params.severite = severite;
  if (actifFilter) params.actif = actifFilter;

  const query = usePagedApi<RegleQualite>("/api/regles-qualite", params);
  const rows = query.data?.data || [];

  useEffect(() => {
    query.setPage(1);
  }, [debounced, severite, actifFilter]);

  const client = useQueryClient();
  const toggleMutation = useMutation({
    mutationFn: (regle: RegleQualite) =>
      apiRequest(`/api/regles-qualite/${regle.regle_id}`, {
        method: "PATCH",
        body: cleanPayload({ actif: !regle.actif }, REGLE_QUALITE_FIELDS)
      }),
    onSettled: () => {
      client.invalidateQueries({ queryKey: ["/api/regles-qualite"] });
      client.invalidateQueries();
    }
  });

  const columns: Column<RegleQualite>[] = [
    { key: "id", header: "ID", render: (row) => row.regle_id, align: "right" },
    { key: "code", header: "Code", render: (row) => row.code_regle },
    { key: "entite", header: "Entite", render: (row) => row.entite },
    { key: "champ", header: "Champ", render: (row) => row.nom_champ || "N/A" },
    { key: "type", header: "Type", render: (row) => row.type_regle || "N/A" },
    { key: "severite", header: "Severite", render: (row) => <StatusBadge value={row.severite} /> },
    { key: "actif", header: "Actif", render: (row) => <StatusBadge value={row.actif ? "ACTIF" : "INACTIF"} /> },
    {
      key: "actions",
      header: "",
      align: "right",
      render: (row) => (
        <Button
          variant={row.actif ? "danger" : "secondary"}
          onClick={() => toggleMutation.mutate(row)}
          disabled={toggleMutation.isPending}
        >
          {row.actif ? "Desactiver" : "Activer"}
        </Button>
      )
    }
  ];

  return (
    <Page title="Regles qualite" eyebrow="Gouvernance">
      {toggleMutation.isError ? <div className="form-error">{toggleMutation.error.message}</div> : null}
      <div className="filter-bar">
        <Input placeholder="Rechercher code, description, entite, champ, type..." value={search} onChange={(event) => setSearch(event.target.value)} />
        <Select value={severite} onChange={(event) => setSeverite(event.target.value)}>
          <option value="">Severite: toutes</option>
          <option value="AVERT">AVERT</option>
          <option value="ERREUR">ERREUR</option>
          <option value="INFO">INFO</option>
          <option value="WARNING">WARNING</option>
          <option value="ERROR">ERROR</option>
          <option value="CRITICAL">CRITICAL</option>
        </Select>
        <Select value={actifFilter} onChange={(event) => setActifFilter(event.target.value)}>
          <option value="">Statut: tous</option>
          <option value="true">Actives</option>
          <option value="false">Inactives</option>
        </Select>
      </div>
      <CrudList query={query} rows={rows} columns={columns} getRowKey={(row) => row.regle_id} />
    </Page>
  );
}
