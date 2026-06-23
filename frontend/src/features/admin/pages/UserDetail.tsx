"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { Activity, ArrowLeft, Bed, Camera, Flag, Salad, Weight } from "lucide-react";
import { LineSeries } from "@/src/components/charts/LineSeries";
import { StatusBadge } from "@/src/components/ui/badge";
import { Button } from "@/src/components/ui/button";
import { ChartCard, MetricCard } from "@/src/components/ui/cards";
import { DataTable, type Column } from "@/src/components/ui/data-table";
import { Field, Select } from "@/src/components/ui/forms";
import { ErrorState, LoadingState } from "@/src/components/ui/states";
import { apiRequest } from "@/src/lib/api";
import { compactDate, formatDate, formatNumber } from "@/src/lib/format";
import type { User } from "@/src/types/domain";

type UserResume = {
  utilisateur: User & { organisation?: { organisation_id: number; nom: string } | null };
  compteurs: {
    mesures_biometriques: number;
    mesures_sommeil: number;
    seances: number;
    plats: number;
    photos: number;
    lignes_journal: number;
  };
  derniers_evenements: {
    derniere_mesure_le?: string | null;
    dernier_sommeil_le?: string | null;
    derniere_seance_le?: string | null;
  };
};

type BiometrieResponse = {
  items: Array<Record<string, any>>;
  latest: Record<string, any> | null;
  charts: Record<string, Array<{ date: string; value: number }>>;
};

type SommeilResponse = {
  items: Array<Record<string, any>>;
  latest: Record<string, any> | null;
  charts: Record<string, Array<{ date: string; value: number }>>;
};

type SeancesResponse = {
  items: Array<Record<string, any>>;
  stats: { total: number; calories_brulees: number; duree_totale: number; types: Array<{ name: string; value: number }> };
};

type NutritionResponse = {
  plats: Array<Record<string, any>>;
  journal: Array<Record<string, any>>;
  stats: { total_plats: number; calories_totales: number; repas_par_type: Array<{ name: string; value: number }>; calories_par_jour: Array<{ date: string; value: number }> };
};

type PhotosResponse = {
  items: Array<Record<string, any>>;
};

type ObjectifsResponse = {
  active: Record<string, any> | null;
  items: Array<Record<string, any>>;
  stats: { total: number; reussis: number; echoues: number; annules: number; en_cours: number };
};

const TABS = ["resume", "biometrie", "sommeil", "seances", "nutrition", "photos", "objectifs"] as const;
type Tab = (typeof TABS)[number];

const TAB_LABELS: Record<Tab, string> = {
  resume: "Resume",
  biometrie: "Biometrie",
  sommeil: "Sommeil",
  seances: "Seances",
  nutrition: "Nutrition",
  photos: "Photos",
  objectifs: "Objectifs"
};

function DetailSection<T>({ title, query, render }: { title: string; query: any; render: (data: T) => React.ReactNode }) {
  if (query.isLoading) return <LoadingState label={`Chargement ${title.toLowerCase()}...`} />;
  if (query.isError) return <ErrorState message={query.error.message} onRetry={() => query.refetch()} />;
  return <>{render(query.data as T)}</>;
}

export function AdminUserDetailPage({ id }: { id: string }) {
  const client = useQueryClient();
  const query = useQuery({
    enabled: Boolean(id),
    queryKey: ["/api/admin/utilisateurs", id, "resume"],
    queryFn: () => apiRequest<UserResume>(`/api/admin/utilisateurs/${id}/resume`)
  });
  const [tab, setTab] = useState<Tab>("resume");
  const [statut, setStatut] = useState("");

  const biometrieQuery = useQuery({
    enabled: Boolean(id) && tab === "biometrie",
    queryKey: ["/api/admin/utilisateurs", id, "biometrie"],
    queryFn: () => apiRequest<BiometrieResponse>(`/api/admin/utilisateurs/${id}/biometrie`)
  });
  const sommeilQuery = useQuery({
    enabled: Boolean(id) && tab === "sommeil",
    queryKey: ["/api/admin/utilisateurs", id, "sommeil"],
    queryFn: () => apiRequest<SommeilResponse>(`/api/admin/utilisateurs/${id}/sommeil`)
  });
  const seancesQuery = useQuery({
    enabled: Boolean(id) && tab === "seances",
    queryKey: ["/api/admin/utilisateurs", id, "seances"],
    queryFn: () => apiRequest<SeancesResponse>(`/api/admin/utilisateurs/${id}/seances`)
  });
  const nutritionQuery = useQuery({
    enabled: Boolean(id) && tab === "nutrition",
    queryKey: ["/api/admin/utilisateurs", id, "nutrition"],
    queryFn: () => apiRequest<NutritionResponse>(`/api/admin/utilisateurs/${id}/nutrition`)
  });
  const photosQuery = useQuery({
    enabled: Boolean(id) && tab === "photos",
    queryKey: ["/api/admin/utilisateurs", id, "photos"],
    queryFn: () => apiRequest<PhotosResponse>(`/api/admin/utilisateurs/${id}/photos`)
  });
  const objectifsQuery = useQuery({
    enabled: Boolean(id) && tab === "objectifs",
    queryKey: ["/api/admin/utilisateurs", id, "objectifs"],
    queryFn: () => apiRequest<ObjectifsResponse>(`/api/admin/utilisateurs/${id}/objectifs`)
  });

  const statutMutation = useMutation({
    mutationFn: (newStatut: string) => apiRequest(`/api/admin/utilisateurs/${id}/statut`, { method: "PATCH", body: { statut: newStatut } }),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["/api/admin/utilisateurs", id, "resume"] });
      client.invalidateQueries({ queryKey: ["/api/utilisateurs"] });
    }
  });

  if (query.isLoading) return <LoadingState label="Chargement de l'utilisateur..." />;
  if (query.isError) return <ErrorState message={query.error.message} onRetry={() => query.refetch()} />;
  const { utilisateur: user, compteurs, derniers_evenements } = query.data!;

  return (
    <section className="page-section">
      <Link href="/admin/utilisateurs" className="back-link">
        <ArrowLeft size={14} /> Retour aux utilisateurs
      </Link>

      <header className="detail-hero">
        <span className="eyebrow">Utilisateur · #{user.utilisateur_id}</span>
        <h1><em>{user.prenom || user.nom_utilisateur} {user.nom || ""}</em></h1>
        <div className="hero-meta">
          <div className="kv"><span>Identifiant</span><strong>{user.nom_utilisateur}</strong></div>
          <div className="kv"><span>Email</span><strong>{user.email || "—"}</strong></div>
          <div className="kv"><span>Role</span><strong><StatusBadge value={user.role} /></strong></div>
          <div className="kv"><span>Statut</span><strong><StatusBadge value={user.statut} /></strong></div>
          <div className="kv"><span>Organisation</span><strong>{user.organisation?.nom || "—"}</strong></div>
        </div>
        <div className="filter-bar" style={{ marginTop: 12 }}>
          <Field label="Modifier le statut">
            <Select value={statut} onChange={(event) => setStatut(event.target.value)}>
              <option value="">Choisir...</option>
              <option value="ACTIF">ACTIF</option>
              <option value="SUSPENDU">SUSPENDU</option>
              <option value="ARCHIVE">ARCHIVE</option>
            </Select>
          </Field>
          <Button disabled={!statut || statutMutation.isPending} onClick={() => statutMutation.mutate(statut)}>
            Appliquer
          </Button>
        </div>
      </header>

      <div className="tab-bar">
        {TABS.map((key) => (
          <Button key={key} variant={tab === key ? "primary" : "secondary"} onClick={() => setTab(key)}>
            {TAB_LABELS[key]}
          </Button>
        ))}
      </div>

      {tab === "resume" ? (
        <>
          <div className="metric-grid">
            <MetricCard label="Mesures biometriques" value={formatNumber(compteurs.mesures_biometriques)} icon={Weight} />
            <MetricCard label="Mesures sommeil" value={formatNumber(compteurs.mesures_sommeil)} icon={Bed} />
            <MetricCard label="Seances" value={formatNumber(compteurs.seances)} icon={Activity} />
            <MetricCard label="Plats" value={formatNumber(compteurs.plats)} icon={Salad} />
            <MetricCard label="Photos" value={formatNumber(compteurs.photos)} icon={Camera} />
            <MetricCard label="Lignes journal" value={formatNumber(compteurs.lignes_journal)} icon={Salad} />
          </div>
          <ChartCard title="Derniers evenements">
            <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: 8 }}>
              <li><span className="muted">Derniere mesure :</span> {formatDate(derniers_evenements.derniere_mesure_le) || "—"}</li>
              <li><span className="muted">Dernier sommeil :</span> {formatDate(derniers_evenements.dernier_sommeil_le) || "—"}</li>
              <li><span className="muted">Derniere seance :</span> {formatDate(derniers_evenements.derniere_seance_le) || "—"}</li>
            </ul>
          </ChartCard>
          <ChartCard title="Profil">
            <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: 8 }}>
              <li><span className="muted">Date de naissance :</span> {formatDate(user.date_naissance) || "—"}</li>
              <li><span className="muted">Genre :</span> {user.genre || "—"}</li>
              <li><span className="muted">Taille :</span> {formatNumber(user.taille_cm, " cm")}</li>
              <li><span className="muted">Inscrit le :</span> {formatDate(user.cree_le) || "—"}</li>
              <li><span className="muted">Derniere modification :</span> {formatDate(user.modifie_le) || "—"}</li>
            </ul>
          </ChartCard>
        </>
      ) : null}

      {tab === "biometrie" ? (
        <DetailSection<BiometrieResponse>
          title="Biometrie"
          query={biometrieQuery}
          render={(data) => (
            !data.items.length ? <div className="state">Aucune donnee biometrique.</div> : <>
              <div className="metric-grid">
                <MetricCard label="Dernier poids" value={formatNumber(data.latest?.poids_kg, " kg")} icon={Weight} />
                <MetricCard label="Dernier IMC" value={formatNumber(data.latest?.imc)} icon={Weight} />
                <MetricCard label="Masse grasse" value={formatNumber(data.latest?.taux_masse_grasse, " %")} icon={Weight} />
                <MetricCard label="BPM repos" value={formatNumber(data.latest?.bpm_repos)} icon={Activity} />
              </div>
              <ChartCard title="Evolution poids / IMC" expandable data={data.charts.poids?.map((row, index) => ({ date: compactDate(row.date), poids: row.value, imc: data.charts.imc?.[index]?.value })) || []}>
                <LineSeries
                  data={data.charts.poids.map((row, index) => ({ date: compactDate(row.date), poids: row.value, imc: data.charts.imc?.[index]?.value }))}
                  xKey="date"
                  series={[{ key: "poids", label: "Poids", color: "#2563eb" }, { key: "imc", label: "IMC", color: "#0284c7" }]}
                />
              </ChartCard>
              <DataTable
                rows={data.items}
                getRowKey={(row) => row.mesure_id}
                columns={[
                  { key: "date", header: "Date", render: (row) => formatDate(row.mesure_le) },
                  { key: "poids", header: "Poids", render: (row) => formatNumber(row.poids_kg, " kg"), align: "right" },
                  { key: "imc", header: "IMC", render: (row) => formatNumber(row.imc), align: "right" },
                  { key: "masse", header: "Masse grasse", render: (row) => formatNumber(row.taux_masse_grasse, " %"), align: "right" },
                  { key: "bpm", header: "BPM", render: (row) => formatNumber(row.bpm_repos || row.bpm_moyen || row.bpm_max), align: "right" },
                ]}
              />
            </>
          )}
        />
      ) : null}

      {tab === "sommeil" ? (
        <DetailSection<SommeilResponse>
          title="Sommeil"
          query={sommeilQuery}
          render={(data) => (
            !data.items.length ? <div className="state">Aucune donnee sommeil.</div> : <>
              <div className="metric-grid">
                <MetricCard label="Dernier sommeil" value={formatNumber(data.latest?.duree_sommeil_h, " h")} icon={Bed} />
                <MetricCard label="Qualite" value={formatNumber(data.latest?.qualite_sommeil_score)} icon={Bed} />
                <MetricCard label="Stress" value={formatNumber(data.latest?.stress_score)} icon={Bed} />
                <MetricCard label="Pas" value={formatNumber(data.latest?.pas_jour)} icon={Activity} />
              </div>
              <ChartCard title="Sommeil / Qualite" expandable data={data.charts.sommeil?.map((row, index) => ({ date: compactDate(row.date), sommeil: row.value, qualite: data.charts.qualite?.[index]?.value })) || []}>
                <LineSeries
                  data={data.charts.sommeil.map((row, index) => ({ date: compactDate(row.date), sommeil: row.value, qualite: data.charts.qualite?.[index]?.value }))}
                  xKey="date"
                  series={[{ key: "sommeil", label: "Sommeil", color: "#2563eb" }, { key: "qualite", label: "Qualite", color: "#0284c7" }]}
                />
              </ChartCard>
              <DataTable
                rows={data.items}
                getRowKey={(row) => row.mesure_sommeil_id}
                columns={[
                  { key: "date", header: "Date", render: (row) => formatDate(row.mesure_le) },
                  { key: "sommeil", header: "Sommeil", render: (row) => formatNumber(row.duree_sommeil_h, " h"), align: "right" },
                  { key: "qualite", header: "Qualite", render: (row) => formatNumber(row.qualite_sommeil_score), align: "right" },
                  { key: "stress", header: "Stress", render: (row) => formatNumber(row.stress_score), align: "right" },
                  { key: "pas", header: "Pas", render: (row) => formatNumber(row.pas_jour), align: "right" },
                ]}
              />
            </>
          )}
        />
      ) : null}

      {tab === "seances" ? (
        <DetailSection<SeancesResponse>
          title="Seances"
          query={seancesQuery}
          render={(data) => (
            !data.items.length ? <div className="state">Aucune seance.</div> : <>
              <div className="metric-grid">
                <MetricCard label="Total seances" value={formatNumber(data.stats.total)} icon={Activity} />
                <MetricCard label="Duree totale" value={formatNumber(data.stats.duree_totale, " min")} icon={Activity} />
                <MetricCard label="Calories brulees" value={formatNumber(data.stats.calories_brulees)} icon={Activity} />
              </div>
              <ChartCard title="Types d'entrainement" empty={!data.stats.types.length} expandable data={data.stats.types}>
                <DataTable
                  rows={data.stats.types}
                  getRowKey={(row) => row.name}
                  columns={[
                    { key: "type", header: "Type", render: (row) => row.name },
                    { key: "nb", header: "Volume", render: (row) => row.value, align: "right" },
                  ]}
                />
              </ChartCard>
              <DataTable
                rows={data.items}
                getRowKey={(row) => row.seance_id}
                columns={[
                  { key: "date", header: "Date", render: (row) => formatDate(row.date_seance) },
                  { key: "type", header: "Type", render: (row) => row.type_entrainement || "—" },
                  { key: "duree", header: "Duree", render: (row) => formatNumber(row.duree_min, " min"), align: "right" },
                  { key: "calories", header: "Calories", render: (row) => formatNumber(row.calories_brulees_estimees), align: "right" },
                  { key: "exos", header: "Exercices", render: (row) => row.exercices?.map((item: any) => item.nom).join(", ") || "—" },
                ]}
              />
            </>
          )}
        />
      ) : null}

      {tab === "nutrition" ? (
        <DetailSection<NutritionResponse>
          title="Nutrition"
          query={nutritionQuery}
          render={(data) => (
            (!data.plats.length && !data.journal.length) ? <div className="state">Aucune donnee nutrition.</div> : <>
              <div className="metric-grid">
                <MetricCard label="Total plats" value={formatNumber(data.stats.total_plats)} icon={Salad} />
                <MetricCard label="Calories totales" value={formatNumber(data.stats.calories_totales)} icon={Salad} />
                <MetricCard label="Repas types" value={formatNumber(data.stats.repas_par_type.length)} icon={Salad} />
              </div>
              <ChartCard title="Calories par jour" expandable data={data.stats.calories_par_jour}>
                <LineSeries
                  data={data.stats.calories_par_jour.map((row) => ({ date: compactDate(row.date), value: row.value }))}
                  xKey="date"
                  series={[{ key: "value", label: "Calories", color: "#2563eb" }]}
                />
              </ChartCard>
              <DataTable
                rows={data.journal}
                getRowKey={(row) => row.journal_id}
                columns={[
                  { key: "date", header: "Date", render: (row) => formatDate(row.consomme_le) },
                  { key: "repas", header: "Repas", render: (row) => row.type_repas || "—" },
                  { key: "item", header: "Element", render: (row) => row.aliment_nom_libre || row.plat_id || row.aliment_id || "—" },
                  { key: "calories", header: "Calories", render: (row) => formatNumber(row.calories_kcal), align: "right" },
                ]}
              />
            </>
          )}
        />
      ) : null}

      {tab === "photos" ? (
        <DetailSection<PhotosResponse>
          title="Photos"
          query={photosQuery}
          render={(data) => (
            !data.items.length ? <div className="state">Aucune photo de progression.</div> : (
              <div className="gallery-grid">
                {data.items.map((photo) => (
                  <figure key={photo.photo_id}>
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src={photo.photo_url} alt={`Photo ${photo.photo_id}`} />
                    <figcaption>
                      <strong>{photo.type_photo || "Photo"}</strong>
                      {formatDate(photo.date_photo) || "—"}
                    </figcaption>
                  </figure>
                ))}
              </div>
            )
          )}
        />
      ) : null}

      {tab === "objectifs" ? (
        <DetailSection<ObjectifsResponse>
          title="Objectifs"
          query={objectifsQuery}
          render={(data) => (
            !data.items.length ? <div className="state">Aucun objectif.</div> : <>
              <div className="metric-grid">
                <MetricCard label="Total" value={formatNumber(data.stats.total)} icon={Flag} />
                <MetricCard label="En cours" value={formatNumber(data.stats.en_cours)} icon={Flag} />
                <MetricCard label="Reussis" value={formatNumber(data.stats.reussis)} icon={Flag} />
                <MetricCard label="Echoues / annules" value={formatNumber(data.stats.echoues + data.stats.annules)} icon={Flag} />
              </div>
              <ChartCard title="Objectif actif">
                {data.active ? (
                  <div className="kv-grid">
                    <div className="kv"><span className="label">Type</span><span className="value">{data.active.type_objectif}</span></div>
                    <div className="kv"><span className="label">Periode</span><span className="value">{formatDate(data.active.date_debut)} - {formatDate(data.active.date_fin)}</span></div>
                    <div className="kv"><span className="label">Statut</span><span className="value"><StatusBadge value={data.active.statut_objectif} /></span></div>
                  </div>
                ) : <div className="muted">Aucun objectif actif.</div>}
              </ChartCard>
              <DataTable
                rows={data.items}
                getRowKey={(row) => row.objectif_id}
                columns={[
                  { key: "type", header: "Type", render: (row) => row.type_objectif },
                  { key: "debut", header: "Debut", render: (row) => formatDate(row.date_debut) },
                  { key: "fin", header: "Fin", render: (row) => formatDate(row.date_fin) },
                  { key: "statut", header: "Statut", render: (row) => <StatusBadge value={row.statut_objectif} /> },
                  { key: "commentaire", header: "Commentaire", render: (row) => row.commentaire || "—" },
                ]}
              />
            </>
          )}
        />
      ) : null}
    </section>
  );
}
