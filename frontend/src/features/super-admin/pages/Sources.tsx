"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Eye } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { StatusBadge } from "@/src/components/ui/badge";
import { Button } from "@/src/components/ui/button";
import type { Column } from "@/src/components/ui/data-table";
import { Field, Input, Textarea } from "@/src/components/ui/forms";
import { Modal } from "@/src/components/ui/modal";
import { usePagedApi } from "@/src/hooks/use-paged-api";
import { apiRequest } from "@/src/lib/api";
import { cleanPayload, SOURCE_DONNEES_FIELDS } from "@/src/lib/payload";
import type { SourceDonnees } from "@/src/types/domain";
import { CrudList, DeleteDialog, Page } from "@/src/features/admin/pages/_shared";

const schema = z.object({
  nom: z.string().min(1),
  description: z.string().optional(),
  type_source: z.string().optional(),
  format_source: z.string().optional()
});
type Form = z.infer<typeof schema>;

export function SuperAdminSourcesPage() {
  const query = usePagedApi<SourceDonnees>("/api/sources-donnees");
  const rows = query.data?.data || [];
  const [editing, setEditing] = useState<SourceDonnees | null>(null);
  const [viewing, setViewing] = useState<SourceDonnees | null>(null);
  const [deleting, setDeleting] = useState<SourceDonnees | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  const client = useQueryClient();
  const toggleMutation = useMutation({
    mutationFn: (source: SourceDonnees) =>
      apiRequest(`/api/sources-donnees/${source.source_id}`, {
        method: "PATCH",
        body: cleanPayload({ actif: !source.actif }, SOURCE_DONNEES_FIELDS)
      }),
    onSettled: () => {
      client.invalidateQueries({ queryKey: ["/api/sources-donnees"] });
      client.invalidateQueries();
    }
  });

  const columns: Column<SourceDonnees>[] = [
    { key: "id", header: "ID", render: (row) => row.source_id, align: "right" },
    { key: "nom", header: "Nom", render: (row) => row.nom },
    { key: "type", header: "Type", render: (row) => row.type_source || "N/A" },
    { key: "format", header: "Format", render: (row) => row.format_source || "N/A" },
    { key: "desc", header: "Description", render: (row) => row.description || "N/A" },
    { key: "actif", header: "Actif", render: (row) => <StatusBadge value={row.actif ? "ACTIF" : "INACTIF"} /> },
    {
      key: "actions",
      header: "",
      align: "right",
      render: (row) => (
        <div className="row-actions">
          <Button variant="secondary" onClick={() => setViewing(row)}><Eye size={15} /> Voir</Button>
          <Button variant="secondary" onClick={() => setEditing(row)}>Editer</Button>
          <Button variant="secondary" disabled={toggleMutation.isPending} onClick={() => toggleMutation.mutate(row)}>
            {row.actif ? "Desactiver" : "Activer"}
          </Button>
          <Button variant="danger" onClick={() => setDeleting(row)}>Supprimer</Button>
        </div>
      )
    }
  ];

  return (
    <Page title="Sources de donnees" eyebrow="Super administration">
      {toggleMutation.isError ? <div className="form-error">{toggleMutation.error.message}</div> : null}
      {feedback ? <div className="form-error">{feedback}</div> : null}
      <CrudList query={query} rows={rows} columns={columns} getRowKey={(row) => row.source_id} />
      <SourceDetail source={viewing} onClose={() => setViewing(null)} onEdit={(source) => { setViewing(null); setEditing(source); }} />
      <SourceModal source={editing} onClose={() => setEditing(null)} />
      <DeleteDialog
        path="/api/sources-donnees"
        id={deleting?.source_id}
        label={deleting?.nom}
        open={Boolean(deleting)}
        onClose={() => setDeleting(null)}
        onSuccess={(payload) => {
          setFeedback(payload?.message || "Source mise a jour.");
        }}
        onError={(error) => setFeedback(error?.message || "Suppression impossible.")}
      />
    </Page>
  );
}

function SourceDetail({
  source,
  onClose,
  onEdit
}: {
  source: SourceDonnees | null;
  onClose: () => void;
  onEdit: (source: SourceDonnees) => void;
}) {
  return (
    <Modal title="Detail source" open={Boolean(source)} onClose={onClose}>
      {source ? (
        <div className="form-stack">
          <div className="kv-grid">
            <div className="kv"><span className="label">ID</span><span className="value">{source.source_id}</span></div>
            <div className="kv"><span className="label">Statut</span><span className="value"><StatusBadge value={source.actif ? "ACTIF" : "INACTIF"} /></span></div>
          </div>
          <div>
            <h3 style={{ margin: "0 0 6px" }}>{source.nom}</h3>
            <p className="muted">{source.description || "Aucune description."}</p>
          </div>
          <div className="kv-grid">
            <div className="kv"><span className="label">Type</span><span className="value">{source.type_source || "N/A"}</span></div>
            <div className="kv"><span className="label">Format</span><span className="value">{source.format_source || "N/A"}</span></div>
          </div>
          <div className="form-actions">
            <Button variant="secondary" onClick={onClose}>Fermer</Button>
            <Button onClick={() => onEdit(source)}>Editer</Button>
          </div>
        </div>
      ) : null}
    </Modal>
  );
}

function SourceModal({ source, onClose }: { source: SourceDonnees | null; onClose: () => void }) {
  const client = useQueryClient();
  const isNew = source && !source.source_id;
  const form = useForm<Form>({
    resolver: zodResolver(schema),
    values: {
      nom: source?.nom || "",
      description: source?.description || "",
      type_source: source?.type_source || "",
      format_source: source?.format_source || ""
    }
  });
  const mutation = useMutation({
    mutationFn: (values: Form) =>
      apiRequest(`/api/sources-donnees${isNew ? "" : `/${source?.source_id}`}`, {
        method: isNew ? "POST" : "PATCH",
        body: cleanPayload(values, SOURCE_DONNEES_FIELDS)
      }),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["/api/sources-donnees"] });
      onClose();
    }
  });
  return (
    <Modal title={isNew ? "Creer une source" : "Modifier source"} open={Boolean(source)} onClose={onClose}>
      <form className="form-stack" onSubmit={form.handleSubmit((values) => mutation.mutate(values))}>
        <Field label="Nom"><Input {...form.register("nom")} /></Field>
        <Field label="Type"><Input {...form.register("type_source")} placeholder="ex: API, fichier, BDD" /></Field>
        <Field label="Format"><Input {...form.register("format_source")} placeholder="ex: csv, json" /></Field>
        <Field label="Description"><Textarea rows={3} {...form.register("description")} /></Field>
        {mutation.isError ? <div className="form-error">{mutation.error.message}</div> : null}
        <div className="form-actions">
          <Button variant="secondary" type="button" onClick={onClose}>Annuler</Button>
          <Button type="submit" disabled={mutation.isPending}>Enregistrer</Button>
        </div>
      </form>
    </Modal>
  );
}
