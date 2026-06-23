"use client";

import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import {
  Activity,
  AlertCircle,
  CalendarCheck,
  Dumbbell,
  HeartPulse,
  Moon,
  Salad,
  Scale,
  Target,
  Weight
} from "lucide-react";
import { ChartCard } from "@/src/components/ui/cards";
import { Button } from "@/src/components/ui/button";
import { EmptyState } from "@/src/components/ui/states";
import {
  HealthKpiCard,
  HealthTimeline,
  type HealthTimelineItem
} from "@/src/components/health/health-widgets";
import { getCoachPostureHistory } from "@/src/features/coach-posture/api";
import type { CoachPostureHistoryItem } from "@/src/features/coach-posture/types";
import { apiList } from "@/src/lib/api";
import { formatDate, formatNumber } from "@/src/lib/format";
import type {
  JournalAlimentaire,
  MesureBiometrique,
  Objectif,
  Plat,
  Seance,
  SommeilSante
} from "@/src/types/domain";
import { Page } from "./_shared";

type HistoryCategory = "all" | "nutrition" | "sport" | "sante" | "objectifs" | "coach";
type HistoryItem = HealthTimelineItem & {
  category: Exclude<HistoryCategory, "all">;
  timestamp: number;
};

const filters: Array<{ value: HistoryCategory; label: string }> = [
  { value: "all", label: "Tout" },
  { value: "nutrition", label: "Nutrition" },
  { value: "sport", label: "Sport" },
  { value: "sante", label: "Sante" },
  { value: "objectifs", label: "Objectifs" },
  { value: "coach", label: "Coach posture" }
];

export function HistoriquePage() {
  const [filter, setFilter] = useState<HistoryCategory>("all");
  const plats = useHistoryList<Plat>("/api/me/plats", "plats");
  const journal = useHistoryList<JournalAlimentaire>("/api/me/journal-alimentaire", "journal");
  const seances = useHistoryList<Seance>("/api/me/seances", "seances");
  const objectifs = useHistoryList<Objectif>("/api/me/objectifs", "objectifs");
  const biometrie = useHistoryList<MesureBiometrique>("/api/me/mesures-biometriques", "biometrie");
  const sommeil = useHistoryList<SommeilSante>("/api/me/sommeil-sante", "sommeil");
  const coach = useQuery({
    queryKey: ["history", "coach-posture"],
    queryFn: () => getCoachPostureHistory(),
    retry: false
  });

  const queries = [plats, journal, seances, objectifs, biometrie, sommeil, coach];
  const loading = queries.some((query) => query.isLoading);
  const errors = queries.filter((query) => query.isError);
  const items = useMemo(
    () =>
      buildHistoryItems({
        plats: plats.data || [],
        journal: journal.data || [],
        seances: seances.data || [],
        objectifs: objectifs.data || [],
        biometrie: biometrie.data || [],
        sommeil: sommeil.data || [],
        coach: coach.data || []
      }),
    [biometrie.data, coach.data, journal.data, objectifs.data, plats.data, seances.data, sommeil.data]
  );
  const filteredItems = filter === "all" ? items : items.filter((item) => item.category === filter);
  const stats = statsFor(items);

  return (
    <Page eyebrow="Activite utilisateur" title="Historique">
      <div className="health-kpi-grid history-kpi-grid">
        <HealthKpiCard label="Evenements" value={items.length} hint="Toutes sources chargees" icon={CalendarCheck} tone="teal" />
        <HealthKpiCard label="Nutrition" value={stats.nutrition} hint="Repas et journal" icon={Salad} tone="green" />
        <HealthKpiCard label="Sport" value={stats.sport + stats.coach} hint="Seances et posture" icon={Dumbbell} tone="blue" />
        <HealthKpiCard label="Sante" value={stats.sante} hint="Biometrie et sommeil" icon={HeartPulse} tone="violet" />
      </div>

      {errors.length ? (
        <div className="history-error-list" role="alert">
          <AlertCircle size={18} aria-hidden />
          <span>
            Certaines sources n'ont pas pu etre chargees. Les donnees disponibles restent affichees sans bloquer la page.
          </span>
        </div>
      ) : null}

      <ChartCard title="Journal chronologique" subtitle="Donnees reelles agregees depuis les endpoints existants">
        <div className="history-toolbar" role="toolbar" aria-label="Filtrer l'historique">
          {filters.map((item) => (
            <Button
              key={item.value}
              variant={filter === item.value ? "primary" : "secondary"}
              onClick={() => setFilter(item.value)}
              aria-pressed={filter === item.value}
              disabled={loading}
            >
              {item.label}
            </Button>
          ))}
        </div>
        {loading ? (
          <div className="history-loading-grid" aria-label="Chargement de l'historique">
            {Array.from({ length: 6 }).map((_, index) => (
              <span className="skeleton history-skeleton-row" key={index} />
            ))}
          </div>
        ) : filteredItems.length ? (
          <HealthTimeline items={filteredItems.slice(0, 80)} emptyLabel="Aucun evenement disponible." />
        ) : (
          <EmptyState label="Aucun evenement pour ce filtre." />
        )}
      </ChartCard>
    </Page>
  );
}

function useHistoryList<T>(path: string, key: string) {
  return useQuery({
    queryKey: ["history", key],
    queryFn: () => apiList<T>(path, { query: { page: 1, page_size: 50 } }).then((response) => response.data),
    retry: false
  });
}

function buildHistoryItems({
  plats,
  journal,
  seances,
  objectifs,
  biometrie,
  sommeil,
  coach
}: {
  plats: Plat[];
  journal: JournalAlimentaire[];
  seances: Seance[];
  objectifs: Objectif[];
  biometrie: MesureBiometrique[];
  sommeil: SommeilSante[];
  coach: CoachPostureHistoryItem[];
}): HistoryItem[] {
  const items: HistoryItem[] = [
    ...plats.map((row) => item({
      id: `plat-${row.plat_id}`,
      category: "nutrition",
      label: "Repas",
      title: row.nom_plat || row.type_repas || "Repas",
      meta: `${formatDate(row.consomme_le)} - ${formatNumber(row.calories_totales_kcal, " kcal")}`,
      date: row.consomme_le,
      href: `/me/nutrition/plats/${row.plat_id}`,
      icon: Salad
    })),
    ...journal.map((row) => item({
      id: `journal-${row.journal_id}`,
      category: "nutrition",
      label: row.type_repas || "Journal alimentaire",
      title: row.aliment_nom_libre || `Aliment #${row.aliment_id || "N/A"}`,
      meta: `${formatDate(row.consomme_le)} - ${formatNumber(row.quantite)} ${row.unite_quantite || ""} - ${formatNumber(row.calories_kcal, " kcal")}`,
      date: row.consomme_le,
      href: row.plat_id ? `/me/nutrition/plats/${row.plat_id}` : "/me/journal-alimentaire",
      icon: Salad
    })),
    ...seances.map((row) => item({
      id: `seance-${row.seance_id}`,
      category: "sport",
      label: "Seance",
      title: row.type_entrainement || "Entrainement",
      meta: `${formatDate(row.date_seance)} - ${formatNumber(row.duree_seance_min, " min")} - ${formatNumber(row.calories_brulees_total, " kcal")}`,
      date: row.date_seance,
      href: `/me/seances/${row.seance_id}`,
      icon: Activity
    })),
    ...objectifs.map((row) => item({
      id: `objectif-${row.objectif_id}`,
      category: "objectifs",
      label: "Objectif",
      title: formatLabel(row.type_objectif),
      meta: `${row.statut_objectif || "Statut inconnu"} - debut ${formatDate(row.date_debut)}`,
      date: row.date_debut || row.date_fin,
      href: "/me/objectifs",
      icon: Target
    })),
    ...biometrie.map((row) => item({
      id: `biometrie-${row.mesure_id}`,
      category: "sante",
      label: "Biometrie",
      title: `Poids ${formatNumber(row.poids_kg, " kg")}`,
      meta: `${formatDate(row.mesure_le)} - IMC ${formatNumber(row.imc)}`,
      date: row.mesure_le,
      href: "/me/mesures-biometriques",
      icon: Weight
    })),
    ...sommeil.map((row) => item({
      id: `sommeil-${row.mesure_sommeil_id}`,
      category: "sante",
      label: "Sommeil",
      title: `${formatNumber(row.duree_sommeil_h, " h")} de sommeil`,
      meta: `${formatDate(row.mesure_le)} - qualite ${formatNumber(row.qualite_sommeil_score)}`,
      date: row.mesure_le,
      href: "/me/sommeil",
      icon: Moon
    })),
    ...coach.map((row) => item({
      id: `coach-${row.validation_id || row.item?.coach_posture_id}`,
      category: "coach",
      label: "Coach posture",
      title: row.exercise_label || row.exercise || "Exercice posture",
      meta: `${formatDate(row.validated_at)} - score ${formatNumber(row.summary?.score_alignement ?? row.item?.score_alignement, " /100")}`,
      date: row.validated_at,
      href: "/me/coach-posture",
      icon: Scale
    }))
  ];

  return items.sort((left, right) => right.timestamp - left.timestamp);
}

function item(input: Omit<HistoryItem, "timestamp">): HistoryItem {
  return { ...input, timestamp: timestamp(input.date) };
}

function timestamp(value?: string | null) {
  if (!value) return 0;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? 0 : date.getTime();
}

function statsFor(items: HistoryItem[]) {
  return items.reduce(
    (acc, current) => {
      acc[current.category] += 1;
      return acc;
    },
    { nutrition: 0, sport: 0, sante: 0, objectifs: 0, coach: 0 }
  );
}

function formatLabel(value?: string | null) {
  return value ? value.replace(/_/g, " ").toLowerCase() : "Non renseigne";
}
