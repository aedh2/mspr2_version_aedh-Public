"use client";

import { useEffect, useMemo, useState } from "react";
import type { Column } from "@/src/components/ui/data-table";
import { SearchInput, Select } from "@/src/components/ui/forms";
import { useDebouncedValue } from "@/src/hooks/use-debounced-value";
import { usePagedApi } from "@/src/hooks/use-paged-api";
import { formatNumber } from "@/src/lib/format";
import type { Aliment } from "@/src/types/domain";
import { ListPage } from "./_shared";

export function AlimentsPage() {
  const [search, setSearch] = useState("");
  const debouncedSearch = useDebouncedValue(search, 300);
  const [categorie, setCategorie] = useState("");

  const params = useMemo(() => {
    const p: Record<string, string> = {};
    if (debouncedSearch) p.search = debouncedSearch;
    if (categorie) p.categorie = categorie;
    return p;
  }, [debouncedSearch, categorie]);

  const query = usePagedApi<Aliment>("/api/aliments", params);
  useEffect(() => {
    query.setPage(1);
  }, [debouncedSearch, categorie]);

  const rows = query.data?.data || [];
  const categories = useMemo(
    () =>
      Array.from(
        new Set(rows.map((row) => row.categorie).filter((c): c is string => Boolean(c)))
      ).sort(),
    [rows]
  );

  const columns: Column<Aliment>[] = [
    { key: "nom", header: "Aliment", render: (row) => row.nom },
    { key: "cat", header: "Categorie", render: (row) => row.categorie || "N/A" },
    { key: "kcal", header: "Calories", render: (row) => formatNumber(row.calories_kcal, " kcal"), align: "right" },
    { key: "prot", header: "Proteines", render: (row) => formatNumber(row.proteines_g, " g"), align: "right" },
    { key: "gluc", header: "Glucides", render: (row) => formatNumber(row.glucides_g, " g"), align: "right" },
    { key: "lip", header: "Lipides", render: (row) => formatNumber(row.lipides_g, " g"), align: "right" },
    { key: "fib", header: "Fibres", render: (row) => formatNumber(row.fibres_g, " g"), align: "right" }
  ];

  const filterBar = (
    <div className="filter-bar">
      <SearchInput
        label="Rechercher un aliment"
        placeholder="Rechercher un aliment..."
        value={search}
        onChange={(event) => setSearch(event.target.value)}
      />
      <Select value={categorie} onChange={(event) => setCategorie(event.target.value)}>
        <option value="">Toutes les categories</option>
        {categories.map((c) => (
          <option key={c} value={c}>{c}</option>
        ))}
      </Select>
    </div>
  );

  return (
    <ListPage
      title="Catalogue d'aliments"
      eyebrow="Reference nutrition"
      query={query}
      rows={rows}
      columns={columns}
      getRowKey={(row) => row.aliment_id}
      filterBar={filterBar}
    />
  );
}
