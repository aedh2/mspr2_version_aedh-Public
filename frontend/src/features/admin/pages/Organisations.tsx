"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2, Eye } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Button } from "@/src/components/ui/button";
import { Field, Input, Textarea } from "@/src/components/ui/forms";
import { Modal } from "@/src/components/ui/modal";
import { ErrorState, LoadingState } from "@/src/components/ui/states";
import { usePagedApi } from "@/src/hooks/use-paged-api";
import { apiRequest } from "@/src/lib/api";
import { formatDate } from "@/src/lib/format";
import type { Organisation } from "@/src/types/domain";
import { cleanPayload, ORGANISATION_FIELDS } from "@/src/lib/payload";
import { DeleteDialog, Page } from "./_shared";

const orgSchema = z.object({
  nom: z.string().min(1),
  adresse: z.string().optional(),
  image_path: z.string().optional()
});
type OrgForm = z.infer<typeof orgSchema>;

export function OrganisationsPage() {
  const query = usePagedApi<Organisation>("/api/organisations");
  const [editing, setEditing] = useState<Organisation | null>(null);
  const [viewing, setViewing] = useState<Organisation | null>(null);
  const [deleting, setDeleting] = useState<Organisation | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  const rows = query.data?.data || [];

  return (
    <Page
      title="Organisations"
      eyebrow="Super administration"
      actions={
        <Button onClick={() => setEditing({} as Organisation)}>
          <Building2 size={16} />
          Creer
        </Button>
      }
    >
      {feedback ? <div className="form-error">{feedback}</div> : null}
      {query.isLoading ? <LoadingState label="Chargement des organisations..." /> : null}
      {query.isError ? <ErrorState message={query.error.message} onRetry={() => query.refetch()} /> : null}
      {!query.isLoading && !query.isError ? (
        <div className="org-grid">
          {rows.map((row) => (
            <article
              className="org-card clickable"
              key={row.organisation_id}
              onClick={() => setViewing(row)}
            >
              <div className="org-card-main">
                {row.image_url || row.image_path ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    className="org-card-image"
                    src={row.image_url || row.image_path || ""}
                    alt={row.nom || "Organisation"}
                  />
                ) : (
                  <div className="org-image-fallback">
                    <Building2 size={26} />
                  </div>
                )}
                <div className="org-card-body">
                  <p className="org-card-label">
                    ORGANISATION #{row.organisation_id}
                  </p>
                  <h3 className="org-card-title">{row.nom}</h3>
                  <p className="org-card-address">
                    {row.adresse || "Adresse non renseignee"}
                  </p>
                  <p className="org-card-date">Cree le {formatDate(row.cree_le)}</p>
                </div>
              </div>
              <div className="org-card-actions">
                <Button
                  variant="secondary"
                  onClick={(event) => { event.stopPropagation(); setViewing(row); }}
                >
                  <Eye size={15} />
                  Voir
                </Button>
                <Button
                  variant="secondary"
                  onClick={(event) => { event.stopPropagation(); setEditing(row); }}
                >
                  Editer
                </Button>
                <Button
                  variant="danger"
                  onClick={(event) => { event.stopPropagation(); setDeleting(row); }}
                >
                  Supprimer
                </Button>
              </div>
            </article>
          ))}
        </div>
      ) : null}
      <OrganisationDetail organisation={viewing} onEdit={(org) => { setViewing(null); setEditing(org); }} onClose={() => setViewing(null)} />
      <OrganisationModal organisation={editing} onClose={() => setEditing(null)} />
      <DeleteDialog
        path="/api/organisations"
        id={deleting?.organisation_id}
        label={deleting?.nom}
        open={Boolean(deleting)}
        onClose={() => setDeleting(null)}
        onSuccess={(payload) => setFeedback(payload?.message || "Organisation supprimee.")}
        onError={(error) => setFeedback(error?.message || "Suppression impossible.")}
      />
    </Page>
  );
}

function OrganisationDetail({
  organisation,
  onClose,
  onEdit
}: {
  organisation: Organisation | null;
  onClose: () => void;
  onEdit: (organisation: Organisation) => void;
}) {
  const stats = useQuery({
    enabled: Boolean(organisation?.organisation_id),
    queryKey: ["/api/super-admin/organisations/stats", organisation?.organisation_id],
    queryFn: () =>
      apiRequest<{
        nb_utilisateurs: number;
        nb_admins: number;
        nb_utilisateurs_actifs: number;
        dernieres_inscriptions: unknown[];
      }>(`/api/super-admin/organisations/${organisation!.organisation_id}/stats`)
  });

  return (
    <Modal title="Detail organisation" open={Boolean(organisation)} onClose={onClose}>
      {organisation ? (
        <div className="org-detail">
          {organisation.image_url || organisation.image_path ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={organisation.image_url || organisation.image_path || ""} alt={organisation.nom} />
          ) : (
            <div className="org-detail-fallback"><Building2 size={38} /></div>
          )}
          <div>
            <span className="eyebrow">Organisation #{organisation.organisation_id}</span>
            <h3>{organisation.nom}</h3>
            <p className="muted">{organisation.adresse || "Adresse non renseignee"}</p>
            <div className="kv-grid">
              <div className="kv"><span className="label">Utilisateurs</span><span className="value">{stats.data?.nb_utilisateurs ?? "..."}</span></div>
              <div className="kv"><span className="label">Admins</span><span className="value">{stats.data?.nb_admins ?? "..."}</span></div>
              <div className="kv"><span className="label">Actifs</span><span className="value">{stats.data?.nb_utilisateurs_actifs ?? "..."}</span></div>
            </div>
            <p className="muted">Image path : {organisation.image_path || "N/A"}</p>
            <p className="muted">Creation : {formatDate(organisation.cree_le)}</p>
          </div>
          <div className="form-actions">
            <Button variant="secondary" onClick={onClose}>Fermer</Button>
            <Button onClick={() => onEdit(organisation)}>Editer</Button>
          </div>
        </div>
      ) : null}
    </Modal>
  );
}

function OrganisationModal({ organisation, onClose }: { organisation: Organisation | null; onClose: () => void }) {
  const client = useQueryClient();
  const isNew = organisation && !organisation.organisation_id;
  const form = useForm<OrgForm>({
    resolver: zodResolver(orgSchema),
    values: {
      nom: organisation?.nom || "",
      adresse: organisation?.adresse || "",
      image_path: organisation?.image_path || ""
    }
  });
  const mutation = useMutation({
    mutationFn: (values: OrgForm) =>
      apiRequest(`/api/organisations${isNew ? "" : `/${organisation?.organisation_id}`}`, {
        method: isNew ? "POST" : "PATCH",
        body: cleanPayload(values, ORGANISATION_FIELDS)
      }),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["/api/organisations"] });
      onClose();
    }
  });
  return (
    <Modal title={isNew ? "Creer une organisation" : "Modifier organisation"} open={Boolean(organisation)} onClose={onClose}>
      <form className="form-stack" onSubmit={form.handleSubmit((values) => mutation.mutate(values))}>
        <Field label="Nom"><Input {...form.register("nom")} /></Field>
        <Field label="Adresse"><Textarea rows={3} {...form.register("adresse")} /></Field>
        <Field label="Image path"><Input {...form.register("image_path")} /></Field>
        {mutation.isError ? <div className="form-error">{mutation.error?.message || "Une erreur est survenue."}</div> : null}
        <div className="form-actions">
          <Button variant="secondary" type="button" onClick={onClose}>Annuler</Button>
          <Button type="submit" disabled={mutation.isPending}>Enregistrer</Button>
        </div>
      </form>
    </Modal>
  );
}
