"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, CircleOff, Flag, Plus, Trophy, XCircle } from "lucide-react";
import { useMemo, useState } from "react";
import { Button } from "@/src/components/ui/button";
import { ChartCard } from "@/src/components/ui/cards";
import { Modal } from "@/src/components/ui/modal";
import { Pagination } from "@/src/components/ui/pagination";
import { EmptyState, ErrorState, LoadingState } from "@/src/components/ui/states";
import { usePagedApi } from "@/src/hooks/use-paged-api";
import { apiRequest } from "@/src/lib/api";
import { cleanPayload, OBJECTIF_FIELDS } from "@/src/lib/payload";
import { formatDate } from "@/src/lib/format";
import type { Objectif } from "@/src/types/domain";
import { Page } from "./_shared";

const OBJECTIF_OPTIONS = [
  { value: "PERTE_POIDS", label: "Perte de poids" },
  { value: "GAIN_MUSCLE", label: "Prise de muscle" },
  { value: "SOMMEIL", label: "Sommeil" },
  { value: "MAINTIEN_FORME", label: "Activite / maintien de forme" },
  { value: "EQUILIBRE_VIE", label: "Equilibre de vie" },
  { value: "AUTRE", label: "Autre" }
];

export function ObjectifsPage() {
  const [adding, setAdding] = useState(false);
  const [selected, setSelected] = useState<Objectif | null>(null);
  const actif = useQuery({
    queryKey: ["/api/me/objectifs/actif"],
    queryFn: () => apiRequest<Objectif>("/api/me/objectifs/actif").catch(() => null),
    retry: false
  });
  const list = usePagedApi<Objectif>("/api/me/objectifs");
  const rows = list.data?.data || [];

  return (
    <Page
      title="Objectifs"
      eyebrow="Suivi"
      actions={<Button onClick={() => setAdding(true)}><Plus size={16} /> Nouvel objectif</Button>}
    >
      <ChartCard title="Objectif actif">
        {actif.isLoading ? (
          <LoadingState />
        ) : actif.data ? (
          <ObjectiveHighlight objectif={actif.data} onClick={() => setSelected(actif.data)} />
        ) : (
          <div className="dashboard-empty-card">
            <EmptyState label="Aucun objectif actif." />
            <Button variant="secondary" onClick={() => setAdding(true)}>Creer un objectif</Button>
          </div>
        )}
      </ChartCard>

      <ChartCard title="Historique des objectifs">
        {list.isLoading ? <LoadingState /> : null}
        {list.isError ? <ErrorState message={list.error.message} onRetry={() => list.refetch()} /> : null}
        {!list.isLoading && !list.isError ? (
          rows.length ? (
            <div className="objective-grid">
              {rows.map((objectif) => (
                <button
                  key={objectif.objectif_id}
                  type="button"
                  className="objective-card"
                  onClick={() => setSelected(objectif)}
                >
                  <div className="objective-card-head">
                    <span className="objective-chip">{objectif.type_objectif}</span>
                    <span className={`objective-status objective-status-${(objectif.statut_objectif || "EN_COURS").toLowerCase()}`}>
                      {objectif.statut_objectif || (objectif.actif_unique ? "EN_COURS" : "TERMINE")}
                    </span>
                  </div>
                  <strong>{formatDate(objectif.date_debut)} {objectif.date_fin ? `→ ${formatDate(objectif.date_fin)}` : "→ En cours"}</strong>
                  <p className="muted">{objectif.commentaire || "Aucun commentaire."}</p>
                </button>
              ))}
            </div>
          ) : (
            <EmptyState label="Aucun objectif disponible." />
          )
        ) : null}
        <Pagination meta={list.data?.meta} page={list.page} onPageChange={list.setPage} />
      </ChartCard>

      <CreateObjectifModal open={adding} onClose={() => setAdding(false)} />
      <ObjectifDetailModal objectif={selected} onClose={() => setSelected(null)} />
    </Page>
  );
}

function ObjectiveHighlight({ objectif, onClick }: { objectif: Objectif; onClick: () => void }) {
  return (
    <button type="button" className="objective-highlight" onClick={onClick}>
      <div className="dashboard-avatar dashboard-avatar-sm">
        <Flag size={18} />
      </div>
      <div>
        <strong>{objectif.type_objectif}</strong>
        <div className="muted">{objectif.statut_objectif || "EN_COURS"}</div>
      </div>
      <div className="dashboard-meta-grid">
        <span><strong>Debut</strong>{formatDate(objectif.date_debut)}</span>
        <span><strong>Fin</strong>{formatDate(objectif.date_fin) || "En cours"}</span>
      </div>
      {objectif.commentaire ? <p className="muted">{objectif.commentaire}</p> : null}
    </button>
  );
}

function CreateObjectifModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const client = useQueryClient();
  const [values, setValues] = useState({
    type_objectif: "PERTE_POIDS",
    date_debut: new Date().toISOString().slice(0, 10),
    date_fin: "",
    commentaire: ""
  });
  const mutation = useMutation({
    mutationFn: () =>
      apiRequest("/api/me/objectifs", {
        method: "POST",
        body: cleanPayload(values, OBJECTIF_FIELDS)
      }),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["/api/me/objectifs"] });
      client.invalidateQueries({ queryKey: ["/api/me/objectifs/actif"] });
      client.invalidateQueries({ queryKey: ["me-dashboard"] });
      setValues({
        type_objectif: "PERTE_POIDS",
        date_debut: new Date().toISOString().slice(0, 10),
        date_fin: "",
        commentaire: ""
      });
      onClose();
    }
  });

  return (
    <Modal title="Nouvel objectif" open={open} onClose={onClose}>
      <form
        className="form-stack"
        onSubmit={(event) => {
          event.preventDefault();
          mutation.mutate();
        }}
      >
        <label className="field">
          <span>Type d'objectif</span>
          <select className="control" value={values.type_objectif} onChange={(event) => setValues((state) => ({ ...state, type_objectif: event.target.value }))}>
            {OBJECTIF_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        </label>
        <div className="profile-form-grid">
          <label className="field">
            <span>Date debut</span>
            <input className="control" type="date" value={values.date_debut} onChange={(event) => setValues((state) => ({ ...state, date_debut: event.target.value }))} />
          </label>
          <label className="field">
            <span>Date fin</span>
            <input className="control" type="date" value={values.date_fin} onChange={(event) => setValues((state) => ({ ...state, date_fin: event.target.value }))} />
          </label>
        </div>
        <label className="field">
          <span>Commentaire</span>
          <textarea className="control" rows={4} value={values.commentaire} onChange={(event) => setValues((state) => ({ ...state, commentaire: event.target.value }))} />
        </label>
        {mutation.isError ? <div className="form-error">{mutation.error.message}</div> : null}
        <div className="form-actions">
          <Button variant="secondary" type="button" onClick={onClose}>Annuler</Button>
          <Button type="submit" disabled={mutation.isPending}>{mutation.isPending ? "Creation..." : "Creer"}</Button>
        </div>
      </form>
    </Modal>
  );
}

function ObjectifDetailModal({ objectif, onClose }: { objectif: Objectif | null; onClose: () => void }) {
  const client = useQueryClient();
  const actionMutation = useMutation({
    mutationFn: (action: "reussir" | "echouer" | "annuler") =>
      apiRequest(`/api/me/objectifs/${objectif?.objectif_id}/${action}`, { method: "PATCH" }),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["/api/me/objectifs"] });
      client.invalidateQueries({ queryKey: ["/api/me/objectifs/actif"] });
      client.invalidateQueries({ queryKey: ["me-dashboard"] });
      onClose();
    }
  });
  const actions = useMemo(() => {
    if (!objectif || (objectif.statut_objectif && objectif.statut_objectif !== "EN_COURS") || !objectif.actif_unique) return [];
    return [
      { key: "reussir" as const, label: "Marquer reussi", icon: Trophy },
      { key: "echouer" as const, label: "Marquer echoue", icon: XCircle },
      { key: "annuler" as const, label: "Annuler l'objectif", icon: CircleOff }
    ];
  }, [objectif]);

  return (
    <Modal title="Detail objectif" open={Boolean(objectif)} onClose={onClose}>
      {objectif ? (
        <div className="form-stack">
          <div className="objective-detail-grid">
            <span><strong>Type</strong>{objectif.type_objectif}</span>
            <span><strong>Statut</strong>{objectif.statut_objectif || "EN_COURS"}</span>
            <span><strong>Date debut</strong>{formatDate(objectif.date_debut)}</span>
            <span><strong>Date fin</strong>{formatDate(objectif.date_fin) || "En cours"}</span>
            <span><strong>Actif</strong>{objectif.actif_unique ? "Oui" : "Non"}</span>
          </div>
          <div className="callout">
            <strong>Commentaire</strong> {objectif.commentaire || "Aucun commentaire."}
          </div>
          {actionMutation.isError ? <div className="form-error">{actionMutation.error.message}</div> : null}
          {actions.length ? (
            <div className="form-actions objective-actions">
              {actions.map((action) => {
                const Icon = action.icon;
                return (
                  <Button key={action.key} variant={action.key === "reussir" ? "primary" : "secondary"} onClick={() => actionMutation.mutate(action.key)} disabled={actionMutation.isPending}>
                    <Icon size={16} /> {action.label}
                  </Button>
                );
              })}
            </div>
          ) : (
            <div className="empty-inline">
              <CheckCircle2 size={16} />
              Objectif clos, aucune action disponible.
            </div>
          )}
        </div>
      ) : null}
    </Modal>
  );
}
