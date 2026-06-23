"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import {
  Activity,
  Bed,
  CalendarCheck,
  ChevronRight,
  Dumbbell,
  Flame,
  Salad,
  Scale,
  Sparkles,
  Target,
  Utensils,
  Weight
} from "lucide-react";
import { LineSeries } from "@/src/components/charts/LineSeries";
import {
  CircularScore,
  CompactDonut,
  DashboardSkeleton,
  HealthKpiCard,
  HealthProgress,
  HealthTimeline,
  type DonutItem,
  type HealthTimelineItem
} from "@/src/components/health/health-widgets";
import { ChartCard } from "@/src/components/ui/cards";
import { EmptyState, ErrorState } from "@/src/components/ui/states";
import { usePagedApi } from "@/src/hooks/use-paged-api";
import { apiRequest } from "@/src/lib/api";
import { compactDate, formatDate, formatNumber } from "@/src/lib/format";
import type {
  JournalAlimentaire,
  MeDashboard,
  MesureBiometrique,
  Objectif,
  Plat,
  ProgressionPhoto,
  Seance,
  SommeilSante
} from "@/src/types/domain";
import { Page } from "./_shared";

const SCORE_WINDOW_DAYS = 30;
const REGULARITY_WINDOW_DAYS = 14;

export function MeDashboardPage() {
  const dashboard = useQuery({
    queryKey: ["me-dashboard"],
    queryFn: () => apiRequest<MeDashboard>("/api/me/dashboard")
  });
  const biometrie = usePagedApi<MesureBiometrique>("/api/me/mesures-biometriques", {}, 18);
  const sommeil = usePagedApi<SommeilSante>("/api/me/sommeil-sante", {}, 18);
  const seances = usePagedApi<Seance>("/api/me/seances", {}, 30);
  const plats = usePagedApi<Plat>("/api/me/plats", {}, 30);
  const journal = usePagedApi<JournalAlimentaire>("/api/me/journal-alimentaire", {}, 60);
  const photos = usePagedApi<ProgressionPhoto>("/api/me/photos", {}, 12);
  const objectif = useQuery({
    queryKey: ["/api/me/objectifs/actif"],
    queryFn: () => apiRequest<Objectif>("/api/me/objectifs/actif").catch(() => null),
    retry: false
  });

  if (dashboard.isLoading) return <DashboardSkeleton />;
  if (dashboard.isError) {
    return <ErrorState message={dashboard.error.message} onRetry={() => dashboard.refetch()} />;
  }

  const data = dashboard.data;
  const biometrieRows = biometrie.data?.data || [];
  const sommeilRows = sommeil.data?.data || [];
  const seanceRows = seances.data?.data || [];
  const platRows = plats.data?.data || [];
  const journalRows = journal.data?.data || [];

  const activeObjectif = objectif.data || data?.objectif_actif || null;
  const latestPhoto = data?.derniere_photo || (photos.data?.data || [])[0];
  const latestSleep = sommeilRows
    .slice()
    .sort((left, right) => timestamp(right.mesure_le) - timestamp(left.mesure_le))[0];
  const weightData = biometrieRows
    .slice()
    .sort((left, right) => timestamp(left.mesure_le) - timestamp(right.mesure_le))
    .map((row) => ({ ...row, label: compactDate(row.mesure_le) }));
  const sleepData = sommeilRows
    .slice()
    .sort((left, right) => timestamp(left.mesure_le) - timestamp(right.mesure_le))
    .map((row) => ({ ...row, label: compactDate(row.mesure_le) }));

  const mealEntries = mealSource(journalRows, platRows);
  const recentMeals = (data?.derniers_repas || platRows).slice(0, 5);
  const recentSeances = (data?.dernieres_seances || seanceRows).slice(0, 5);
  const activeDays = activeDaySet(mealEntries, seanceRows, sommeilRows, biometrieRows, REGULARITY_WINDOW_DAYS);
  const mealDays30 = uniqueDays(mealEntries.map((entry) => entry.date), SCORE_WINDOW_DAYS);
  const seances30 = seanceRows.filter((row) => isWithinDays(row.date_seance, SCORE_WINDOW_DAYS));
  const caloriesAverage = averageDailyCalories(mealEntries);
  const mealsPerDay = averagePerDay(mealEntries.map((entry) => entry.date), SCORE_WINDOW_DAYS);
  const bestStreak = computeBestStreak([
    ...mealEntries.map((entry) => entry.date),
    ...seanceRows.map((row) => row.date_seance),
    ...sommeilRows.map((row) => row.mesure_le)
  ]);
  const weightDelta = computeWeightDelta(biometrieRows);
  const nutritionScore = computeNutritionScore(mealEntries, mealDays30.size);
  const activityScore = computeActivityScore(seances30);
  const sleepScore = computeSleepScore(latestSleep, data?.derniere_duree_sommeil_h);
  const regularityScore = activeDays.size ? Math.round((activeDays.size / REGULARITY_WINDOW_DAYS) * 100) : null;
  const readinessScore = averageScore([nutritionScore, activityScore, sleepScore, regularityScore]);
  const mealDonut = mealTypeDonut(mealEntries);
  const priorities = buildPriorities({
    nutritionScore,
    activityScore,
    sleepScore,
    regularityScore,
    hasMacroData: false,
    activeObjectif
  });
  const summary = buildPersonalSummary({
    readinessScore,
    nutritionScore,
    activityScore,
    sleepScore,
    regularityScore,
    activeObjectif
  });
  const timeline = buildRecentTimeline(recentMeals, recentSeances, activeObjectif).slice(0, 6);

  return (
    <Page
      eyebrow="Application personnelle"
      title="Tableau de bord HealthAI"
      subtitle="Synthese sante, nutrition, sport et regularite calculee avec les donnees disponibles."
    >
      <section className="health-dashboard-hero" aria-label="Synthese sante">
        <div className="health-readiness-panel">
          <CircularScore label="Readiness score" value={readinessScore} helper="Moyenne des signaux disponibles" tone="teal" />
          <div>
            <p className="eyebrow">Aujourd'hui</p>
            <h2>Vue d'ensemble personnelle</h2>
            <p>
              Score calcule depuis les donnees disponibles: nutrition, activite, sommeil et regularite. Les donnees
              manquantes ne sont pas inventees.
            </p>
          </div>
        </div>
        <div className="health-score-grid" aria-label="Scores secondaires">
          <CircularScore label="Nutrition" value={nutritionScore} helper={mealEntries.length ? "Repas et calories" : "Aucun repas recent"} tone="green" />
          <CircularScore label="Activite" value={activityScore} helper={seances30.length ? "Seances 30 jours" : "Aucune seance recente"} tone="blue" />
          <CircularScore label="Sommeil" value={sleepScore} helper={latestSleep ? "Derniere mesure" : "Donnee indisponible"} tone="violet" />
          <CircularScore label="Regularite" value={regularityScore} helper={`${activeDays.size}/${REGULARITY_WINDOW_DAYS} jours actifs`} tone="amber" />
        </div>
      </section>

      <div className="health-kpi-grid">
        <HealthKpiCard label="Poids actuel" value={formatNumber(data?.dernier_poids_kg, " kg")} hint={weightDeltaHint(weightDelta)} icon={Weight} tone="teal" href="/me/mesures-biometriques" />
        <HealthKpiCard label="IMC" value={formatNumber(data?.dernier_imc)} hint={imcHint(data?.dernier_imc)} icon={Scale} tone="blue" href="/me/mesures-biometriques" />
        <HealthKpiCard label="Calories moyennes" value={formatNumber(caloriesAverage, " kcal")} hint="Moyenne/jour sur donnees recentes" icon={Flame} tone="amber" href="/me/journal-alimentaire" />
        <HealthKpiCard label="Repas par jour" value={formatNumber(mealsPerDay)} hint="Moyenne 30 jours" icon={Utensils} tone="green" href="/me/journal-alimentaire" />
        <HealthKpiCard label="Seances" value={data?.nb_seances ?? 0} hint={`${seances30.length} sur 30 jours`} icon={Dumbbell} tone="blue" href="/me/seances" />
        <HealthKpiCard label="Sommeil" value={formatNumber(data?.derniere_duree_sommeil_h, " h")} hint={latestSleep?.qualite_sommeil_score ? `Qualite ${latestSleep.qualite_sommeil_score}/100` : "Derniere duree"} icon={Bed} tone="violet" href="/me/sommeil" />
        <HealthKpiCard label="Proteines atteintes" value="Indisponible" hint="Non expose par le journal actuel" icon={Salad} tone="red" href="/me/nutrition" />
        <HealthKpiCard label="Meilleure serie" value={bestStreak ? `${bestStreak} j` : "N/A"} hint="Jours consecutifs avec activite suivie" icon={CalendarCheck} tone="teal" href="/me/historique" />
      </div>

      <div className="health-dashboard-grid">
        <ChartCard title="Progression poids / IMC" subtitle={weightData.length ? "Mesures biometriques reelles" : "Aucune mesure disponible"} expandable data={weightData}>
          {weightData.length ? (
            <LineSeries
              data={weightData}
              xKey="label"
              series={[
                { key: "poids_kg", label: "Poids", color: "#2563eb" },
                { key: "imc", label: "IMC", color: "#0284c7" }
              ]}
            />
          ) : (
            <EmptyState label="Ajoute une mesure biometrique pour suivre ton poids." />
          )}
        </ChartCard>
        <ChartCard title="Sommeil" subtitle={sleepData.length ? "Duree et qualite" : "Donnee sommeil indisponible"} expandable data={sleepData}>
          {sleepData.length ? (
            <LineSeries
              data={sleepData}
              xKey="label"
              series={[
                { key: "duree_sommeil_h", label: "Sommeil (h)", color: "#7c3aed" },
                { key: "qualite_sommeil_score", label: "Qualite", color: "#0284c7" }
              ]}
            />
          ) : (
            <EmptyState label="Aucune mesure de sommeil a afficher." />
          )}
        </ChartCard>
      </div>

      <div className="health-dashboard-grid health-dashboard-grid-3">
        <ChartCard title="Nutrition" subtitle="Repas, calories et disponibilite macros">
          <div className="health-panel-stack">
            <CompactDonut label="Repas par type" items={mealDonut} emptyLabel="Aucun repas recent" />
            <HealthProgress label="Equilibre macro" value={null} helper="Proteines, glucides et lipides ne sont pas encore exposes dans le journal utilisateur." tone="teal" />
            <HealthProgress label="Objectif proteines" value={null} helper="Cible proteines a calculer apres exposition des macros." tone="green" />
          </div>
        </ChartCard>

        <ChartCard title="Recommandations prioritaires" subtitle="Priorites locales, sans appel IA automatique">
          <div className="health-priority-list">
            {priorities.map((item) => (
              <Link key={item.title} href={item.href} className="health-priority-card">
                <span className={`health-priority-dot health-priority-${item.tone}`} aria-hidden />
                <span>
                  <strong>{item.title}</strong>
                  <small>{item.description}</small>
                </span>
                <ChevronRight size={15} aria-hidden />
              </Link>
            ))}
          </div>
        </ChartCard>

        <ChartCard title="Conseil personnalise" subtitle="Fallback local base sur tes donnees">
          <article className="health-insight-card">
            <span className={`health-insight-icon health-insight-${summary.tone}`}>
              <Sparkles size={18} aria-hidden />
            </span>
            <div>
              <strong>{summary.title}</strong>
              <p>{summary.description}</p>
              <Link href="/me/recommandations" className="row-open-hint">
                Obtenir recommandations <ChevronRight size={14} />
              </Link>
            </div>
          </article>
        </ChartCard>
      </div>

      <div className="health-dashboard-grid">
        <ChartCard title="Historique recent" subtitle="Repas, seances et objectif actif">
          <HealthTimeline items={timeline} emptyLabel="Aucune action recente disponible." />
          <Link href="/me/historique" className="health-section-link">
            Voir tout l'historique <ChevronRight size={14} />
          </Link>
        </ChartCard>

        <ChartCard title="Prochains objectifs" subtitle="Suivi de l'objectif utilisateur">
          {activeObjectif ? (
            <div className="health-objective-panel">
              <div className="health-objective-icon">
                <Target size={18} aria-hidden />
              </div>
              <div>
                <p className="eyebrow">Objectif actif</p>
                <h3>{formatObjective(activeObjectif.type_objectif)}</h3>
                <div className="health-objective-meta">
                  <span><strong>Debut</strong>{formatDate(activeObjectif.date_debut)}</span>
                  <span><strong>Fin</strong>{activeObjectif.date_fin ? formatDate(activeObjectif.date_fin) : "En cours"}</span>
                </div>
                {activeObjectif.commentaire ? <p className="muted">{activeObjectif.commentaire}</p> : null}
                <Link href="/me/objectifs" className="row-open-hint">
                  Gerer les objectifs <ChevronRight size={14} />
                </Link>
              </div>
            </div>
          ) : (
            <div className="dashboard-empty-card">
              <EmptyState label="Aucun objectif actif pour le moment." />
              <Link href="/me/objectifs" className="row-open-hint">
                Definir un objectif <ChevronRight size={14} />
              </Link>
            </div>
          )}
          {latestPhoto?.photo_url || latestPhoto?.image_url || latestPhoto?.image_path ? (
            <div className="health-photo-mini">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={latestPhoto.photo_url || latestPhoto.image_url || latestPhoto.image_path || ""}
                alt={latestPhoto.type_photo || "Photo de progression"}
                loading="lazy"
              />
              <span>{formatDate(latestPhoto.prise_le)}</span>
            </div>
          ) : null}
        </ChartCard>
      </div>
    </Page>
  );
}

type MealEntry = {
  id: string;
  date?: string | null;
  calories?: number | null;
  type?: string | null;
};

function mealSource(journalRows: JournalAlimentaire[], platRows: Plat[]): MealEntry[] {
  if (journalRows.length) {
    return journalRows.map((row) => ({
      id: `journal-${row.journal_id}`,
      date: row.consomme_le,
      calories: row.calories_kcal,
      type: row.type_repas
    }));
  }
  return platRows.map((row) => ({
    id: `plat-${row.plat_id}`,
    date: row.consomme_le,
    calories: row.calories_totales_kcal,
    type: row.type_repas
  }));
}

function timestamp(value?: string | null) {
  if (!value) return 0;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? 0 : date.getTime();
}

function dayKey(value?: string | null) {
  const time = timestamp(value);
  if (!time) return null;
  return new Date(time).toISOString().slice(0, 10);
}

function isWithinDays(value?: string | null, days = SCORE_WINDOW_DAYS) {
  const time = timestamp(value);
  if (!time) return false;
  const limit = Date.now() - days * 24 * 60 * 60 * 1000;
  return time >= limit;
}

function uniqueDays(values: Array<string | null | undefined>, days: number) {
  const set = new Set<string>();
  values.forEach((value) => {
    const key = dayKey(value);
    if (key && isWithinDays(value, days)) set.add(key);
  });
  return set;
}

function activeDaySet(
  meals: MealEntry[],
  seances: Seance[],
  sommeil: SommeilSante[],
  biometrie: MesureBiometrique[],
  days: number
) {
  return uniqueDays(
    [
      ...meals.map((entry) => entry.date),
      ...seances.map((row) => row.date_seance),
      ...sommeil.map((row) => row.mesure_le),
      ...biometrie.map((row) => row.mesure_le)
    ],
    days
  );
}

function averageDailyCalories(meals: MealEntry[]) {
  const byDay = new Map<string, number>();
  meals.forEach((entry) => {
    if (!isWithinDays(entry.date, SCORE_WINDOW_DAYS)) return;
    const key = dayKey(entry.date);
    if (!key || entry.calories === null || entry.calories === undefined) return;
    byDay.set(key, (byDay.get(key) || 0) + entry.calories);
  });
  if (!byDay.size) return null;
  return Math.round(Array.from(byDay.values()).reduce((sum, value) => sum + value, 0) / byDay.size);
}

function averagePerDay(values: Array<string | null | undefined>, days: number) {
  const recent = values.filter((value) => isWithinDays(value, days));
  if (!recent.length) return null;
  return Math.round((recent.length / days) * 10) / 10;
}

function computeNutritionScore(meals: MealEntry[], activeMealDays: number) {
  const recentMeals = meals.filter((entry) => isWithinDays(entry.date, SCORE_WINDOW_DAYS));
  if (!recentMeals.length) return null;
  const regularity = Math.min(1, activeMealDays / 18) * 55;
  const frequency = Math.min(1, recentMeals.length / (SCORE_WINDOW_DAYS * 2.5)) * 30;
  const calorieCoverage = recentMeals.some((entry) => typeof entry.calories === "number") ? 15 : 0;
  return Math.round(regularity + frequency + calorieCoverage);
}

function computeActivityScore(seances: Seance[]) {
  if (!seances.length) return null;
  const sessionScore = Math.min(1, seances.length / 12) * 70;
  const totalMinutes = seances.reduce((sum, row) => sum + (row.duree_seance_min || 0), 0);
  const durationScore = Math.min(1, totalMinutes / 600) * 30;
  return Math.round(sessionScore + durationScore);
}

function computeSleepScore(latestSleep?: SommeilSante, fallbackHours?: number | null) {
  if (latestSleep?.qualite_sommeil_score !== null && latestSleep?.qualite_sommeil_score !== undefined) {
    return Math.max(0, Math.min(100, Math.round(latestSleep.qualite_sommeil_score)));
  }
  const hours = latestSleep?.duree_sommeil_h ?? fallbackHours;
  if (hours === null || hours === undefined) return null;
  return Math.max(0, Math.min(100, Math.round(100 - Math.abs(7.5 - hours) * 18)));
}

function averageScore(values: Array<number | null>) {
  const clean = values.filter((value): value is number => value !== null && Number.isFinite(value));
  if (!clean.length) return null;
  return Math.round(clean.reduce((sum, value) => sum + value, 0) / clean.length);
}

function computeBestStreak(values: Array<string | null | undefined>) {
  const sorted = Array.from(uniqueDays(values, 365)).sort();
  let best = 0;
  let current = 0;
  let previous = 0;
  sorted.forEach((day) => {
    const time = timestamp(day);
    if (!previous || time - previous === 24 * 60 * 60 * 1000) current += 1;
    else current = 1;
    best = Math.max(best, current);
    previous = time;
  });
  return best;
}

function computeWeightDelta(rows: MesureBiometrique[]) {
  const clean = rows
    .filter((row) => row.poids_kg !== null && row.poids_kg !== undefined)
    .sort((left, right) => timestamp(left.mesure_le) - timestamp(right.mesure_le));
  if (clean.length < 2) return null;
  return Number(((clean[clean.length - 1].poids_kg || 0) - (clean[0].poids_kg || 0)).toFixed(1));
}

function mealTypeDonut(meals: MealEntry[]): DonutItem[] {
  const counts = new Map<string, number>();
  meals
    .filter((entry) => isWithinDays(entry.date, SCORE_WINDOW_DAYS))
    .forEach((entry) => {
      const label = (entry.type || "Repas").replace(/_/g, " ").toLowerCase();
      counts.set(label, (counts.get(label) || 0) + 1);
    });
  return Array.from(counts.entries()).map(([label, value]) => ({ label, value }));
}

function weightDeltaHint(delta: number | null) {
  if (delta === null) return "Evolution indisponible";
  if (delta === 0) return "Stable sur les mesures connues";
  return `${delta > 0 ? "+" : ""}${formatNumber(delta, " kg")} depuis la premiere mesure`;
}

function imcHint(imc?: number | null) {
  if (imc === null || imc === undefined) return "Donnee indisponible";
  if (imc < 18.5) return "Sous le seuil de reference";
  if (imc < 25) return "Zone de reference OMS";
  if (imc < 30) return "Surveillance recommandee";
  return "Suivi medical recommande";
}

function buildPriorities({
  nutritionScore,
  activityScore,
  sleepScore,
  regularityScore,
  hasMacroData,
  activeObjectif
}: {
  nutritionScore: number | null;
  activityScore: number | null;
  sleepScore: number | null;
  regularityScore: number | null;
  hasMacroData: boolean;
  activeObjectif: Objectif | null;
}) {
  const priorities: Array<{ title: string; description: string; href: string; tone: "green" | "blue" | "amber" | "red" | "violet" }> = [];
  if (nutritionScore === null || nutritionScore < 55) {
    priorities.push({
      title: "Consolider le suivi nutrition",
      description: "Ajoute davantage de repas pour fiabiliser calories, regularite et recommandations.",
      href: "/me/journal-alimentaire",
      tone: "green"
    });
  }
  if (!hasMacroData) {
    priorities.push({
      title: "Completer les macronutriments",
      description: "Les proteines, glucides et lipides ne sont pas encore disponibles dans le dashboard.",
      href: "/me/nutrition",
      tone: "amber"
    });
  }
  if (activityScore === null || activityScore < 55) {
    priorities.push({
      title: "Relancer l'activite",
      description: "Planifie des seances compatibles avec ton niveau et ton materiel.",
      href: "/me/recommandations",
      tone: "blue"
    });
  }
  if (sleepScore !== null && sleepScore < 60) {
    priorities.push({
      title: "Surveiller la recuperation",
      description: "Le signal sommeil baisse le score global: ajoute des mesures et ajuste l'intensite.",
      href: "/me/sommeil",
      tone: "violet"
    });
  }
  if (regularityScore === null || regularityScore < 50) {
    priorities.push({
      title: "Ameliorer la regularite",
      description: "Le coach devient meilleur avec des donnees plus continues.",
      href: "/me/historique",
      tone: "red"
    });
  }
  if (!activeObjectif) {
    priorities.push({
      title: "Definir un objectif",
      description: "Un objectif actif aide le moteur a prioriser nutrition et sport.",
      href: "/me/objectifs",
      tone: "amber"
    });
  }
  return priorities.slice(0, 4);
}

function buildPersonalSummary({
  readinessScore,
  nutritionScore,
  activityScore,
  sleepScore,
  regularityScore,
  activeObjectif
}: {
  readinessScore: number | null;
  nutritionScore: number | null;
  activityScore: number | null;
  sleepScore: number | null;
  regularityScore: number | null;
  activeObjectif: Objectif | null;
}) {
  if (readinessScore === null) {
    return {
      tone: "amber" as const,
      title: "Donnees insuffisantes",
      description: "Ajoute un repas, une seance ou une mesure de sommeil pour obtenir un conseil personnalise fiable."
    };
  }
  const weakest = [
    { key: "nutrition", label: "nutrition", value: nutritionScore },
    { key: "activite", label: "activite", value: activityScore },
    { key: "sommeil", label: "sommeil", value: sleepScore },
    { key: "regularite", label: "regularite", value: regularityScore }
  ]
    .filter((item): item is { key: string; label: string; value: number } => item.value !== null)
    .sort((left, right) => left.value - right.value)[0];

  if (readinessScore >= 75) {
    return {
      tone: "green" as const,
      title: "Base solide",
      description: `Ton suivi est coherent${activeObjectif ? ` avec l'objectif ${formatObjective(activeObjectif.type_objectif).toLowerCase()}` : ""}. Le prochain gain vient surtout du detail nutrition et de la regularite.`
    };
  }
  return {
    tone: "blue" as const,
    title: "Priorite claire",
    description: weakest
      ? `Le signal le plus faible est ${weakest.label}. Lance les recommandations pour obtenir des plats et seances adaptes aux contraintes connues.`
      : "Le score est calcule avec les donnees presentes. Complete ton profil pour rendre les conseils plus precis."
  };
}

function buildRecentTimeline(meals: Plat[], seances: Seance[], activeObjectif: Objectif | null): HealthTimelineItem[] {
  const items: HealthTimelineItem[] = [
    ...meals.map((meal) => ({
      id: `meal-${meal.plat_id}`,
      label: "Repas",
      title: meal.nom_plat || meal.type_repas || "Repas",
      meta: `${formatDate(meal.consomme_le)} - ${formatNumber(meal.calories_totales_kcal, " kcal")}`,
      date: meal.consomme_le,
      href: `/me/nutrition/plats/${meal.plat_id}`,
      icon: Salad
    })),
    ...seances.map((seance) => ({
      id: `seance-${seance.seance_id}`,
      label: "Seance",
      title: seance.type_entrainement || "Seance",
      meta: `${formatDate(seance.date_seance)} - ${formatNumber(seance.duree_seance_min, " min")}`,
      date: seance.date_seance,
      href: `/me/seances/${seance.seance_id}`,
      icon: Activity
    }))
  ];
  if (activeObjectif) {
    items.push({
      id: `objectif-${activeObjectif.objectif_id}`,
      label: "Objectif",
      title: formatObjective(activeObjectif.type_objectif),
      meta: activeObjectif.statut_objectif || "En cours",
      date: activeObjectif.date_debut,
      href: "/me/objectifs",
      icon: Target
    });
  }
  return items.sort((left, right) => timestamp(right.date) - timestamp(left.date));
}

function formatObjective(value?: string | null) {
  if (!value) return "Objectif";
  return value.replace(/_/g, " ").toLowerCase();
}
