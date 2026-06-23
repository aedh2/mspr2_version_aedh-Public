"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Apple } from "lucide-react";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Button } from "@/src/components/ui/button";
import type { Column } from "@/src/components/ui/data-table";
import { Field, Input, SearchInput } from "@/src/components/ui/forms";
import { Modal } from "@/src/components/ui/modal";
import { useDebouncedValue } from "@/src/hooks/use-debounced-value";
import { usePagedApi } from "@/src/hooks/use-paged-api";
import { apiRequest } from "@/src/lib/api";
import { cleanPayload, ALIMENT_FIELDS } from "@/src/lib/payload";
import { formatNumber } from "@/src/lib/format";
import type { Aliment } from "@/src/types/domain";
import { CrudList, DeleteDialog, Page, RowActions } from "./_shared";

const numericString = z.union([z.string(), z.number()]).optional();

const alimentSchema = z.object({
  nom: z.string().min(1),
  categorie: z.string().optional(),
  calories_kcal: numericString,
  proteines_g: numericString,
  glucides_g: numericString,
  lipides_g: numericString,
  fibres_g: numericString,
  sucres_g: numericString,
  sodium_mg: numericString,
  cholesterol_mg: numericString
});
type AlimentForm = z.infer<typeof alimentSchema>;

export function AdminAlimentsPage() {
  const [search, setSearch] = useState("");
  const debounced = useDebouncedValue(search, 300);
  const query = usePagedApi<Aliment>("/api/aliments", debounced ? { q: debounced } : {});
  const rows = query.data?.data || [];
  const [editing, setEditing] = useState<Aliment | null>(null);
  const [deleting, setDeleting] = useState<Aliment | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);

  useEffect(() => {
    query.setPage(1);
  }, [debounced]);

  const columns: Column<Aliment>[] = [
    { key: "id", header: "ID", render: (row) => row.aliment_id, align: "right" },
    { key: "nom", header: "Nom", render: (row) => row.nom },
    { key: "categorie", header: "Categorie", render: (row) => row.categorie || "N/A" },
    { key: "kcal", header: "Calories", render: (row) => formatNumber(row.calories_kcal), align: "right" },
    { key: "prot", header: "Proteines (g)", render: (row) => formatNumber(row.proteines_g), align: "right" },
    { key: "gluc", header: "Glucides (g)", render: (row) => formatNumber(row.glucides_g), align: "right" },
    { key: "lip", header: "Lipides (g)", render: (row) => formatNumber(row.lipides_g), align: "right" },
    {
      key: "actions",
      header: "",
      align: "right",
      render: (row) => <RowActions onEdit={() => setEditing(row)} onDelete={() => setDeleting(row)} />
    }
  ];

  return (
    <Page
      title="Catalogue aliments"
      eyebrow="Referentiels admin"
      actions={
        <Button onClick={() => setEditing({} as Aliment)}>
          <Apple size={16} />
          Creer
        </Button>
      }
    >
      {feedback ? <div className="form-error">{feedback}</div> : null}
      <div className="filter-bar">
        <SearchInput label="Rechercher un aliment" placeholder="Rechercher..." value={search} onChange={(event) => setSearch(event.target.value)} />
      </div>
      <CrudList query={query} rows={rows} columns={columns} getRowKey={(row) => row.aliment_id} />
      <AlimentModal aliment={editing} onClose={() => setEditing(null)} />
      <DeleteDialog
        path="/api/aliments"
        id={deleting?.aliment_id}
        label={deleting?.nom}
        open={Boolean(deleting)}
        onClose={() => setDeleting(null)}
        onSuccess={(payload) => setFeedback(payload?.message || "Aliment supprime.")}
        onError={(error) => setFeedback(error?.message || "Suppression impossible.")}
      />
    </Page>
  );
}

function AlimentModal({ aliment, onClose }: { aliment: Aliment | null; onClose: () => void }) {
  const client = useQueryClient();
  const isNew = aliment && !aliment.aliment_id;
  const form = useForm<AlimentForm>({
    resolver: zodResolver(alimentSchema),
    values: {
      nom: aliment?.nom || "",
      categorie: aliment?.categorie || "",
      calories_kcal: aliment?.calories_kcal ?? "",
      proteines_g: aliment?.proteines_g ?? "",
      glucides_g: aliment?.glucides_g ?? "",
      lipides_g: aliment?.lipides_g ?? "",
      fibres_g: aliment?.fibres_g ?? "",
      sucres_g: aliment?.sucres_g ?? "",
      sodium_mg: aliment?.sodium_mg ?? "",
      cholesterol_mg: aliment?.cholesterol_mg ?? ""
    }
  });
  const mutation = useMutation({
    mutationFn: (values: AlimentForm) => {
      return apiRequest(`/api/aliments${isNew ? "" : `/${aliment?.aliment_id}`}`, {
        method: isNew ? "POST" : "PATCH",
        body: cleanPayload(values, ALIMENT_FIELDS)
      });
    },
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["/api/aliments"] });
      onClose();
    },
    onError: (error: any) => {
      console.error("Erreur:", error.message);
    }
  });
  return (
    <Modal title={isNew ? "Creer un aliment" : "Modifier aliment"} open={Boolean(aliment)} onClose={onClose}>
      <form className="form-stack" onSubmit={form.handleSubmit((values) => mutation.mutate(values))}>
        <Field label="Nom"><Input {...form.register("nom")} /></Field>
        <Field label="Categorie"><Input {...form.register("categorie")} /></Field>
        <Field label="Calories (kcal)"><Input type="number" step="0.01" {...form.register("calories_kcal")} /></Field>
        <Field label="Proteines (g)"><Input type="number" step="0.01" {...form.register("proteines_g")} /></Field>
        <Field label="Glucides (g)"><Input type="number" step="0.01" {...form.register("glucides_g")} /></Field>
        <Field label="Lipides (g)"><Input type="number" step="0.01" {...form.register("lipides_g")} /></Field>
        <Field label="Fibres (g)"><Input type="number" step="0.01" {...form.register("fibres_g")} /></Field>
        <Field label="Sucres (g)"><Input type="number" step="0.01" {...form.register("sucres_g")} /></Field>
        <Field label="Sodium (mg)"><Input type="number" step="0.01" {...form.register("sodium_mg")} /></Field>
        <Field label="Cholesterol (mg)"><Input type="number" step="0.01" {...form.register("cholesterol_mg")} /></Field>
        {mutation.isError ? (
          <div className="form-error">
            {mutation.error?.message || "Une erreur est survenue lors de l'enregistrement."}
          </div>
        ) : null}
        <div className="form-actions">
          <Button variant="secondary" type="button" onClick={onClose}>Annuler</Button>
          <Button type="submit" disabled={mutation.isPending}>{mutation.isPending ? "..." : "Enregistrer"}</Button>
        </div>
      </form>
    </Modal>
  );
}
