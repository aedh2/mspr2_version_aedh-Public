"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle2,
  Dumbbell,
  Loader2,
  Salad,
  ShieldCheck,
  Sparkles,
  Target,
  UtensilsCrossed
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { ConstraintBadgeList, RecommendationCard } from "@/src/components/health/recommendation-card";
import { Button } from "@/src/components/ui/button";
import { ChartCard, MetricCard } from "@/src/components/ui/cards";
import { Field, Input, Select, Textarea } from "@/src/components/ui/forms";
import { EmptyState, ErrorState, LoadingState } from "@/src/components/ui/states";
import { joinList, splitList } from "@/src/features/me/profile-form-utils";
import { apiRequest, getAuthToken } from "@/src/lib/api";
import { formatNumber } from "@/src/lib/format";
import type {
  NutritionRecommendation,
  RecommendationRequest,
  RecommendationResponse,
  SportExerciseRecommendation,
  SportSessionRecommendation,
  User
} from "@/src/types/domain";
import { Page } from "./_shared";

type BudgetValue = "" | "faible" | "moyen" | "eleve";
type SportLevelValue = "" | "debutant" | "intermediaire" | "avance";
type RecommendationMode = "nutrition" | "sport";
type MealTimeValue = "" | "rapide" | "moyen" | "pas_de_contrainte";
type MealTypeValue = "" | "petit_dejeuner" | "dejeuner" | "diner" | "collation" | "gouter";
type PlaceValue = "" | "maison" | "salle" | "exterieur" | "sans_preference";
type SessionTypeValue = "" | "force" | "cardio" | "mobilite" | "recuperation" | "corps_complet" | "musculation";

type MealFormState = {
  objectif_principal: string;
  culture_alimentaire: string;
  regime_alimentaire: string;
  allergies: string;
  preferences_alimentaires: string;
  aliments_evites: string;
  contraintes_sante: string;
  type_repas: MealTypeValue;
  temps_preparation: MealTimeValue;
  budget: BudgetValue;
};

type SportFormState = {
  objectif_principal: string;
  niveau_sportif: SportLevelValue;
  hasEquipment: boolean;
  equipement_disponible: string;
  contraintes_sante: string;
  duree_seance_min: string;
  lieu: PlaceValue;
  type_seance: SessionTypeValue;
  muscles_cibles: string[];
  hasLimitation: boolean;
  douleur_limitation: string;
};

const muscleOptions = [
  { value: "jambes", label: "Jambes" },
  { value: "dos", label: "Dos" },
  { value: "poitrine", label: "Poitrine" },
  { value: "epaules", label: "Epaules" },
  { value: "bras", label: "Bras" },
  { value: "abdominaux", label: "Abdominaux" },
  { value: "fessiers", label: "Fessiers" }
];

const initialMealForm: MealFormState = {
  objectif_principal: "",
  culture_alimentaire: "",
  regime_alimentaire: "",
  allergies: "",
  preferences_alimentaires: "",
  aliments_evites: "",
  contraintes_sante: "",
  type_repas: "",
  temps_preparation: "",
  budget: ""
};

const initialSportForm: SportFormState = {
  objectif_principal: "",
  niveau_sportif: "",
  hasEquipment: false,
  equipement_disponible: "",
  contraintes_sante: "",
  duree_seance_min: "",
  lieu: "",
  type_seance: "",
  muscles_cibles: [],
  hasLimitation: false,
  douleur_limitation: ""
};

export function RecommandationsPage() {
  const router = useRouter();
  const [selectedMode, setSelectedMode] = useState<RecommendationMode | null>(null);
  const [mealForm, setMealForm] = useState<MealFormState>(initialMealForm);
  const [sportForm, setSportForm] = useState<SportFormState>(initialSportForm);
  const [profileLoaded, setProfileLoaded] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [savedSeanceId, setSavedSeanceId] = useState<number | null>(null);

  const profile = useQuery({
    queryKey: ["/api/me/profile"],
    queryFn: () => apiRequest<User>("/api/me/profile")
  });

  useEffect(() => {
    if (!profile.data || profileLoaded) return;
    setMealForm(mealFormFromProfile(profile.data));
    setSportForm(sportFormFromProfile(profile.data));
    setProfileLoaded(true);
  }, [profile.data, profileLoaded]);

  const mutation = useMutation({
    mutationFn: async (payload: RecommendationRequest): Promise<RecommendationResponse> => {
      const token = getAuthToken();
      const response = await fetch("/api/ai/recommandations", {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { authorization: `Bearer ${token}` } : {})
        },
        body: JSON.stringify(payload)
      });
      if (!response.ok) throw new Error(`Erreur ${response.status}`);
      const data = await response.json() as {
        sport_tips: string[];
        nutrition_tips: string[];
        meal_plan: { day: string; meals: { name: string; description?: string; justification?: string; recette?: string; calories?: number; proteins_g?: number; carbs_g?: number; fats_g?: number }[] }[];
        training_plan: { nom: string; muscles: string[]; series: number; repetitions: string; repos: string; intensite: string; description: string; duree_min?: number; justification?: string; gif_url?: string; nom_db?: string; body_part?: string; equipement_necessaire?: string[]; exercice_id_db?: number | null; calories?: number }[];
        source: string;
      };
      const mode = payload.max_sport && payload.max_sport > 1 ? "sport" : "nutrition";
      const contexte = {
        utilisateur_id: 0,
        objectif_principal: payload.objectif_principal || "sante",
        age: null as number | null,
        imc: null as number | null,
        niveau_sportif: payload.niveau_sportif || "",
        duree_seance_min: payload.duree_seance_min || null,
        donnees_utilisees: ["profil utilisateur", "IA Ollama"]
      };
      if (mode === "nutrition") {
        return {
          nutrition: data.meal_plan.flatMap((day) =>
            day.meals.map((meal) => ({
              nom: meal.name,
              type: "plat" as const,
              justification: meal.justification || meal.description || "",
              score_pertinence: 80,
              score_securite: 85,
              score_nutritionnel: 75,
              calories_estimees: meal.calories || 0,
              proteines_g: meal.proteins_g || 0,
              glucides_g: meal.carbs_g || 0,
              lipides_g: meal.fats_g || 0,
              ingredients: [meal.description || meal.name],
              preparation: meal.recette || meal.description || "",
              recette: "",
              alternatives: [],
              badges: [day.day],
              contraintes_respectees: [],
              allergenes_exclus: [],
              budget_estime: null,
              source: "ollama",
              aliment_id: null
            }))
          ),
          sport: { seances: [], exercices: [] },
          generated_at: new Date().toISOString(),
          source: (data.source ?? "external_ai") as RecommendationResponse["source"],
          fallback_utilise: false,
          fallback_message: null,
          contexte,
          contraintes_prises_en_compte: [],
          messages: data.nutrition_tips
        };
      }
      const exercices = (data.training_plan || []).map((ex, i) => ({
        exercice_id: i,
        nom: ex.nom,
        duree_min: ex.duree_min || 0,
        intensite: ex.intensite || "moderee",
        frequence: `${ex.series} séries`,
        equipement_necessaire: ex.equipement_necessaire || [],
        muscles_cibles: ex.muscles || [],
        niveau_adapte: payload.niveau_sportif || "intermediaire",
        score_pertinence: 80,
        score_securite: 85,
        justification: ex.justification || ex.description || "",
        series: ex.series,
        repetitions: ex.repetitions,
        repos: ex.repos,
        contre_indications: [],
        contraintes_respectees: [],
        gif_url: ex.gif_url || null,
        nom_db: ex.nom_db || null,
        exercice_id_db: ex.exercice_id_db ?? null,
        calories_brulees: ex.calories ?? 0,
      }));
      return {
        nutrition: [],
        sport: {
          seances: [{
            nom: "Plan d'entraînement personnalisé par IA",
            justification: data.sport_tips[0] || "",
            duree_min: payload.duree_seance_min || 60,
            intensite: "moderee",
            frequence: "3x/semaine",
            materiel_necessaire: payload.equipement_disponible || [],
            muscles_cibles: payload.muscles_cibles || [],
            exercices,
            contre_indications: []
          }],
          exercices
        },
        generated_at: new Date().toISOString(),
        source: (data.source ?? "external_ai") as RecommendationResponse["source"],
        fallback_utilise: false,
        fallback_message: null,
        contexte,
        contraintes_prises_en_compte: [],
        messages: data.sport_tips
      };
    }
  });

  const saveSeanceMutation = useMutation({
    mutationFn: async (): Promise<{ seance_id: number; exercices_enregistres: number }> => {
      const token = getAuthToken();
      const exercices = (result?.sport.exercices || []).map((ex) => ({
        nom: ex.nom,
        exercice_id_db: ex.exercice_id_db ?? null,
        series: ex.series ?? null,
        repetitions: ex.repetitions ?? null,
        repos: ex.repos ?? null,
        duree_min: ex.duree_min ?? null,
        intensite: ex.intensite ?? null,
        calories: ex.calories_brulees ?? null,
        justification: ex.justification ?? null,
        muscles: ex.muscles_cibles ?? []
      }));
      const totalDuree = exercices.reduce((sum, ex) => sum + (ex.duree_min || 0), 0);
      const response = await fetch("/api/ai/seances", {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { authorization: `Bearer ${token}` } : {})
        },
        body: JSON.stringify({
          type_seance: sportForm.type_seance || "MUSCULATION",
          duree_min: Number(sportForm.duree_seance_min) || totalDuree || null,
          niveau: sportForm.niveau_sportif || null,
          objectif: sportForm.objectif_principal || null,
          exercices
        })
      });
      if (!response.ok) throw new Error(`Erreur ${response.status}`);
      return response.json();
    },
    onSuccess: (data) => setSavedSeanceId(data.seance_id)
  });

  const payload = useMemo<RecommendationRequest>(() => {
    if (selectedMode === "sport") return buildSportPayload(sportForm);
    return buildMealPayload(mealForm);
  }, [mealForm, selectedMode, sportForm]);

  const result = mutation.data;
  const nutritionScore = average(result?.nutrition.map((item) => item.score_pertinence));
  const sportScore = average(result?.sport.exercices.map((item) => item.score_pertinence));
  const safetyScore = selectedMode === "sport"
    ? average(result?.sport.exercices.map((item) => item.score_securite))
    : average(result?.nutrition.map((item) => item.score_securite));

  const submitRecommendations = () => {
    if (!selectedMode || mutation.isPending) return;
    if (selectedMode === "sport" && sportForm.hasLimitation && !sportForm.douleur_limitation.trim()) {
      setFormError("Precise la douleur ou la limitation actuelle avant de generer une seance.");
      return;
    }
    setFormError(null);
    setSavedSeanceId(null);
    saveSeanceMutation.reset();
    mutation.mutate(payload);
  };

  const chooseMode = (mode: RecommendationMode) => {
    setSelectedMode(mode);
    setFormError(null);
    setSavedSeanceId(null);
    saveSeanceMutation.reset();
    mutation.reset();
  };

  if (profile.isLoading) return <LoadingState />;
  if (profile.isError) return <ErrorState message={profile.error.message} onRetry={() => profile.refetch()} />;

  return (
    <Page eyebrow="Coach HealthAI" title="Recommandations">
      <section className="recommendations-intro" aria-labelledby="recommendations-intro-title">
        <div>
          <p className="eyebrow">Accompagnement personnalise</p>
          <h2 id="recommendations-intro-title">Bienvenue dans vos recommandations personnalisees HealthAI</h2>
          <p>Choisissez le type de recommandation, puis ajustez uniquement les champs utiles pour cette demande.</p>
        </div>
      </section>

      <div className="recommendation-choice-grid" role="list" aria-label="Type de recommandation">
        <ChoiceCard
          mode="nutrition"
          selected={selectedMode === "nutrition"}
          icon={<UtensilsCrossed size={24} aria-hidden />}
          title="Recommandation repas et recettes"
          description="Plats, recettes, calories, macros, ingredients, alternatives et justification."
          onSelect={chooseMode}
        />
        <ChoiceCard
          mode="sport"
          selected={selectedMode === "sport"}
          icon={<Dumbbell size={24} aria-hidden />}
          title="Recommandation seance de sport"
          description="Seance complete, exercices, duree, intensite, materiel, muscles, frequence et justification."
          onSelect={chooseMode}
        />
      </div>

      {!selectedMode ? (
        <ChartCard title="Choisissez une recommandation">
          <EmptyState label="Selectionnez une carte repas ou sport pour afficher le formulaire correspondant." />
        </ChartCard>
      ) : (
        <div className="recommendations-layout recommendations-workspace">
          <section className="recommendations-panel" aria-labelledby="recommendation-form-title">
            <div>
              <p className="eyebrow">{selectedMode === "nutrition" ? "Repas et recettes" : "Seance de sport"}</p>
              <h2 id="recommendation-form-title">
                {selectedMode === "nutrition" ? "Formulaire repas" : "Formulaire sport"}
              </h2>
              <p className="muted">Certaines valeurs sont préremplies depuis votre profil.</p>
            </div>

            <form
              className="recommendations-form"
              onSubmit={(event) => {
                event.preventDefault();
                submitRecommendations();
              }}
            >
              {selectedMode === "nutrition" ? (
                <MealRecommendationForm form={mealForm} setForm={setMealForm} />
              ) : (
                <SportRecommendationForm form={sportForm} setForm={setSportForm} />
              )}

              {formError ? <div className="form-error" role="alert">{formError}</div> : null}
              {mutation.isError ? (
                <div className="form-error" role="alert">
                  {mutation.error instanceof Error ? mutation.error.message : "Impossible de generer les recommandations."}
                </div>
              ) : null}
              <div className="form-actions objective-actions">
                <Button type="submit" disabled={mutation.isPending} aria-busy={mutation.isPending}>
                  {mutation.isPending ? <Loader2 className="spin" size={16} /> : <Sparkles size={16} />}
                  {mutation.isPending ? "Generation..." : "Generer"}
                </Button>
              </div>
            </form>
          </section>

          <section className="recommendations-results" aria-live="polite">
            {!result && !mutation.isPending ? (
              <div className="recommendations-empty">
                <EmptyState label="Generez une recommandation pour afficher des cartes detaillees et explicables." />
              </div>
            ) : null}

            {mutation.isPending ? <RecommendationSkeleton mode={selectedMode} /> : null}

            {result ? (
              <>
                <div className="metric-grid recommendation-score-grid">
                  {selectedMode === "nutrition" ? (
                    <MetricCard label="Repas" value={formatNumber(nutritionScore, " /100")} icon={Salad} />
                  ) : (
                    <MetricCard label="Sport" value={formatNumber(sportScore, " /100")} icon={Dumbbell} />
                  )}
                  <MetricCard label="Securite" value={formatNumber(safetyScore, " /100")} icon={ShieldCheck} />
                  <MetricCard
                    label="Source"
                    value={result.source === "local_rules" ? "Fallback local" : "IA externe"}
                    icon={Sparkles}
                  />
                </div>

                <RecommendationContextCard result={result} mode={selectedMode} />

                {selectedMode === "nutrition" ? (
                  <ChartCard title="Recommandations de plats et recettes" subtitle="Resultats compatibles avec les contraintes visibles.">
                    {result.nutrition.length ? (
                      <div className="recommendation-card-list">
                        {result.nutrition.map((item) => (
                          <NutritionCard
                            key={`${item.source}-${item.aliment_id}-${item.nom}`}
                            item={item}
                            excludedAllergens={uniqueList([
                              ...splitList(mealForm.allergies),
                              ...splitList(mealForm.aliments_evites)
                            ])}
                          />
                        ))}
                      </div>
                    ) : (
                      <EmptyState label="Aucune recommandation repas compatible avec toutes les contraintes." />
                    )}
                  </ChartCard>
                ) : (
                  <ChartCard title="Recommandations de seance de sport" subtitle="Seance et exercices ordonnes.">
                    <div className="recommendation-card-list">
                      {result.sport.seances.map((session) => <SessionCard key={session.nom} session={session} />)}
                      {result.sport.exercices.length ? (
                        result.sport.exercices.map((item) => <SportCard key={item.exercice_id} item={item} />)
                      ) : (
                        <EmptyState label="Aucune recommandation sport compatible avec toutes les contraintes." />
                      )}
                    </div>
                    {result.sport.exercices.length ? (
                      <div className="seance-save-action">
                        {savedSeanceId ? (
                          <div className="seance-save-success" role="status">
                            <CheckCircle2 size={18} />
                            <span>Seance enregistree dans votre historique.</span>
                            <Button variant="secondary" onClick={() => router.push(`/me/seances/${savedSeanceId}`)}>
                              Voir la seance
                            </Button>
                          </div>
                        ) : (
                          <>
                            <Button
                              onClick={() => saveSeanceMutation.mutate()}
                              disabled={saveSeanceMutation.isPending}
                              aria-busy={saveSeanceMutation.isPending}
                            >
                              {saveSeanceMutation.isPending ? <Loader2 className="spin" size={16} /> : <Dumbbell size={16} />}
                              {saveSeanceMutation.isPending ? "Enregistrement..." : "Ajouter la seance a mon historique"}
                            </Button>
                            {saveSeanceMutation.isError ? (
                              <div className="form-error" role="alert">
                                Impossible d'enregistrer la seance. Reessayez.
                              </div>
                            ) : null}
                          </>
                        )}
                      </div>
                    ) : null}
                  </ChartCard>
                )}
              </>
            ) : null}
          </section>
        </div>
      )}
    </Page>
  );
}

function ChoiceCard({
  mode,
  selected,
  icon,
  title,
  description,
  onSelect
}: {
  mode: RecommendationMode;
  selected: boolean;
  icon: ReactNode;
  title: string;
  description: string;
  onSelect: (mode: RecommendationMode) => void;
}) {
  return (
    <button
      type="button"
      className={selected ? "recommendation-choice-card selected" : "recommendation-choice-card"}
      aria-pressed={selected}
      onClick={() => onSelect(mode)}
    >
      <span className="recommendation-choice-icon">{icon}</span>
      <span>
        <strong>{title}</strong>
        <small>{description}</small>
      </span>
    </button>
  );
}

function MealRecommendationForm({
  form,
  setForm
}: {
  form: MealFormState;
  setForm: (form: MealFormState) => void;
}) {
  const update = <K extends keyof MealFormState>(key: K, value: MealFormState[K]) => setForm({ ...form, [key]: value });

  return (
    <div className="recommendations-form-section recommendations-form-section-flat">
      <Field label="Objectif principal">
        <Select value={form.objectif_principal} onChange={(event) => update("objectif_principal", event.target.value)}>
          <option value="">Utiliser l'objectif actif</option>
          <option value="PERTE_POIDS">Perte de poids</option>
          <option value="MAINTIEN_FORME">Maintien</option>
          <option value="GAIN_MUSCLE">Prise de masse</option>
          <option value="EQUILIBRE_VIE">Sante</option>
          <option value="PERFORMANCE">Performance</option>
        </Select>
      </Field>
      <Field label="Culture / cuisine alimentaire">
        <Input
          value={form.culture_alimentaire}
          placeholder="Ex: mediterraneenne, asiatique, traditionnelle"
          onChange={(event) => update("culture_alimentaire", event.target.value)}
        />
      </Field>
      <Field label="Regime alimentaire">
        <Input
          value={form.regime_alimentaire}
          placeholder="Ex: vegetarien, sans gluten"
          onChange={(event) => update("regime_alimentaire", event.target.value)}
        />
      </Field>
      <Field label="Allergies">
        <Input
          value={form.allergies}
          placeholder="Ex: arachide, lactose"
          onChange={(event) => update("allergies", event.target.value)}
        />
      </Field>
      <Field label="Preferences alimentaires">
        <Input
          value={form.preferences_alimentaires}
          placeholder="Ex: riz, legumes"
          onChange={(event) => update("preferences_alimentaires", event.target.value)}
        />
      </Field>
      <Field label="Aliments evites">
        <Input
          value={form.aliments_evites}
          placeholder="Ex: thon, plats epices"
          onChange={(event) => update("aliments_evites", event.target.value)}
        />
      </Field>
      <Field label="Contraintes sante">
        <Textarea
          rows={3}
          value={form.contraintes_sante}
          placeholder="Ex: diabete, hypertension, cardiaque"
          onChange={(event) => update("contraintes_sante", event.target.value)}
        />
      </Field>
      <div className="recommendations-form-grid">
        <Field label="Type de repas">
          <Select value={form.type_repas} onChange={(event) => update("type_repas", event.target.value as MealTypeValue)}>
            <option value="">Non precise</option>
            <option value="petit_dejeuner">Petit dejeuner</option>
            <option value="dejeuner">Dejeuner</option>
            <option value="diner">Diner</option>
            <option value="collation">Collation</option>
            <option value="gouter">Gouter</option>
          </Select>
        </Field>
        <Field label="Temps de preparation">
          <Select value={form.temps_preparation} onChange={(event) => update("temps_preparation", event.target.value as MealTimeValue)}>
            <option value="">Non precise</option>
            <option value="rapide">Rapide</option>
            <option value="moyen">Moyen</option>
            <option value="pas_de_contrainte">Pas de contrainte</option>
          </Select>
        </Field>
        <Field label="Budget">
          <Select value={form.budget} onChange={(event) => update("budget", event.target.value as BudgetValue)}>
            <option value="">Non precise</option>
            <option value="faible">Faible</option>
            <option value="moyen">Moyen</option>
            <option value="eleve">Eleve</option>
          </Select>
        </Field>
      </div>
    </div>
  );
}

function SportRecommendationForm({
  form,
  setForm
}: {
  form: SportFormState;
  setForm: (form: SportFormState) => void;
}) {
  const update = <K extends keyof SportFormState>(key: K, value: SportFormState[K]) => setForm({ ...form, [key]: value });
  const toggleMuscle = (muscle: string) => {
    update(
      "muscles_cibles",
      form.muscles_cibles.includes(muscle)
        ? form.muscles_cibles.filter((item) => item !== muscle)
        : [...form.muscles_cibles, muscle]
    );
  };

  return (
    <div className="recommendations-form-section recommendations-form-section-flat">
      <Field label="Objectif principal">
        <Select value={form.objectif_principal} onChange={(event) => update("objectif_principal", event.target.value)}>
          <option value="">Utiliser l'objectif actif</option>
          <option value="PERTE_POIDS">Perte de poids</option>
          <option value="MAINTIEN_FORME">Maintien</option>
          <option value="GAIN_MUSCLE">Prise de masse</option>
          <option value="EQUILIBRE_VIE">Sante</option>
          <option value="PERFORMANCE">Performance</option>
        </Select>
      </Field>
      <Field label="Niveau sportif">
        <Select value={form.niveau_sportif} onChange={(event) => update("niveau_sportif", event.target.value as SportLevelValue)}>
          <option value="">Depuis le profil si disponible</option>
          <option value="debutant">Debutant</option>
          <option value="intermediaire">Intermediaire</option>
          <option value="avance">Avance</option>
        </Select>
      </Field>
      <label className="checkbox-row">
        <input
          type="checkbox"
          checked={form.hasEquipment}
          onChange={(event) => update("hasEquipment", event.target.checked)}
        />
        <span>J'ai du materiel disponible</span>
      </label>
      {form.hasEquipment ? (
        <Field label="Equipement disponible">
          <Input
            value={form.equipement_disponible}
            placeholder="Ex: tapis, halteres, elastique"
            onChange={(event) => update("equipement_disponible", event.target.value)}
          />
        </Field>
      ) : null}
      <Field label="Contre-indications sante">
        <Textarea
          rows={3}
          value={form.contraintes_sante}
          placeholder="Ex: hypertension, genou fragile"
          onChange={(event) => update("contraintes_sante", event.target.value)}
        />
      </Field>
      <div className="recommendations-form-grid">
        <Field label="Duree de seance">
          <Input
            type="number"
            min="5"
            max="240"
            value={form.duree_seance_min}
            onChange={(event) => update("duree_seance_min", event.target.value)}
          />
        </Field>
        <Field label="Lieu">
          <Select value={form.lieu} onChange={(event) => update("lieu", event.target.value as PlaceValue)}>
            <option value="">Sans preference</option>
            <option value="maison">Maison</option>
            <option value="salle">Salle de sport</option>
            <option value="exterieur">Exterieur</option>
            <option value="sans_preference">Sans preference</option>
          </Select>
        </Field>
        <Field label="Type de seance">
          <Select value={form.type_seance} onChange={(event) => update("type_seance", event.target.value as SessionTypeValue)}>
            <option value="">Non precise</option>
            <option value="force">Force</option>
            <option value="cardio">Cardio</option>
            <option value="mobilite">Mobilite</option>
            <option value="recuperation">Recuperation</option>
            <option value="corps_complet">Corps complet</option>
            <option value="musculation">Musculation</option>
          </Select>
        </Field>
      </div>
      {form.type_seance === "musculation" ? (
        <fieldset className="muscle-fieldset">
          <legend>Muscles a travailler</legend>
          <div className="muscle-choice-grid">
            {muscleOptions.map((muscle) => (
              <label key={muscle.value} className="checkbox-chip">
                <input
                  type="checkbox"
                  checked={form.muscles_cibles.includes(muscle.value)}
                  onChange={() => toggleMuscle(muscle.value)}
                />
                <span>{muscle.label}</span>
              </label>
            ))}
          </div>
        </fieldset>
      ) : null}
      <label className="checkbox-row">
        <input
          type="checkbox"
          checked={form.hasLimitation}
          onChange={(event) => update("hasLimitation", event.target.checked)}
        />
        <span>J'ai une douleur ou une limitation actuelle</span>
      </label>
      {form.hasLimitation ? (
        <Field label="Douleur ou limitation actuelle" error={!form.douleur_limitation.trim() ? "Champ obligatoire si la case est cochee." : undefined}>
          <Textarea
            rows={3}
            required
            value={form.douleur_limitation}
            placeholder="Ex: genou sensible aujourd'hui"
            onChange={(event) => update("douleur_limitation", event.target.value)}
          />
        </Field>
      ) : null}
    </div>
  );
}

function RecommendationSkeleton({ mode }: { mode: RecommendationMode }) {
  return (
    <div className="recommendations-skeleton" role="status" aria-label="Generation en cours">
      <div className="state">
        <Loader2 className="spin" size={18} />
        {mode === "nutrition" ? "Calcul des repas compatibles..." : "Construction de la seance compatible..."}
      </div>
      <div className="recommendation-skeleton-grid">
        <span />
        <span />
        <span />
      </div>
    </div>
  );
}

function RecommendationContextCard({ result, mode }: { result: RecommendationResponse; mode: RecommendationMode }) {
  return (
    <ChartCard title="Contexte pris en compte" subtitle={result.fallback_message || undefined}>
      <div className="recommendations-context">
        {result.fallback_utilise ? (
          <div className="recommendations-warning" role="status">
            <AlertTriangle size={16} />
            <span>{result.fallback_message || "Fallback local utilise pour garantir une reponse exploitable."}</span>
          </div>
        ) : null}
        <div className="recommendations-context-grid">
          <ContextItem label="Type" value={mode === "nutrition" ? "Repas" : "Sport"} />
          <ContextItem label="Objectif" value={result.contexte.objectif_principal.replace(/_/g, " ")} />
          <ContextItem label="Age" value={formatNullable(result.contexte.age)} />
          <ContextItem label="IMC" value={formatNullable(result.contexte.imc)} />
          <ContextItem label="Niveau" value={result.contexte.niveau_sportif} />
          <ContextItem label="Duree" value={result.contexte.duree_seance_min ? `${result.contexte.duree_seance_min} min` : "N/A"} />
          <ContextItem label="Source" value={result.source === "local_rules" ? "Moteur local" : "IA externe"} />
        </div>
        <div className="recommendations-context-block">
          <strong>Contraintes respectees</strong>
          <ConstraintBadgeList items={[...result.contexte.donnees_utilisees, ...result.contraintes_prises_en_compte]} />
        </div>
        {result.messages.length ? (
          <div className="recommendations-message-list">
            {result.messages.map((message) => (
              <div className="recommendations-message" key={message}>
                <CheckCircle2 size={16} />
                <span>{message}</span>
              </div>
            ))}
          </div>
        ) : null}
      </div>
    </ChartCard>
  );
}

function NutritionCard({ item, excludedAllergens }: { item: NutritionRecommendation; excludedAllergens: string[] }) {
  const allergens = uniqueList([...(item.allergenes_exclus || []), ...excludedAllergens]);
  return (
    <RecommendationCard
      eyebrow={item.type}
      title={item.nom}
      description=""
      justification={item.justification}
      score={item.score_pertinence}
      safetyScore={item.score_securite}
      confidenceScore={Math.round((item.score_pertinence + item.score_securite + item.score_nutritionnel) / 3)}
      metrics={[
        { label: "Calories", value: item.calories_estimees, suffix: " kcal" },
        { label: "Proteines", value: item.proteines_g, suffix: " g" },
        { label: "Glucides", value: item.glucides_g, suffix: " g" },
        { label: "Lipides", value: item.lipides_g, suffix: " g" }
      ]}
      details={[
        { label: "Ingredients", value: listText(item.ingredients) || item.nom },
        { label: "Preparation", value: item.preparation || item.recette },
        { label: "Budget estime", value: budgetLabel(item.budget_estime) || extractBudget(item.badges) },
        { label: "Allergenes exclus", value: allergens.length ? allergens.join(", ") : "aucune" }
      ]}
      badges={[...item.badges, ...item.contraintes_respectees]}
      alternatives={item.alternatives}
    />
  );
}

function SessionCard({ session }: { session: SportSessionRecommendation }) {
  return (
    <article className="recommendation-session-card">
      <div>
        <p className="eyebrow">Seance complete</p>
        <h3>{session.nom}</h3>
        <p>{session.justification}</p>
      </div>
      <div className="recommendation-session-meta">
        <span><Target size={15} />{session.duree_min} min</span>
        <span>{session.intensite}</span>
        <span>{session.frequence}</span>
        <span>Materiel: {listText(session.materiel_necessaire) || "sans materiel specifique"}</span>
        <span>Muscles: {listText(session.muscles_cibles) || "adaptes au catalogue"}</span>
      </div>
      <ol className="recommendation-exercise-list">
        {session.exercices.map((exercise, index) => (
          <li key={exercise.exercice_id}>
            <span>{index + 1}</span>
            <div>
              <strong>{exercise.nom}</strong>
              <small>
                {exercise.series ? `${exercise.series} series` : "Series adaptees"} - {exercise.repetitions || `${exercise.duree_min} min`} - repos {exercise.repos || "adapte"}
              </small>
            </div>
          </li>
        ))}
      </ol>
      {session.contre_indications?.length ? (
        <div className="recommendations-warning" role="note">
          <AlertTriangle size={16} />
          <span>{session.contre_indications.join(" ")}</span>
        </div>
      ) : null}
    </article>
  );
}

function SportCard({ item }: { item: SportExerciseRecommendation }) {
  return (
    <div className="sport-card-with-gif">
      {item.gif_url ? (
        <div className="sport-card-gif-wrapper">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={item.gif_url}
            alt={`Démonstration : ${item.nom_db || item.nom}`}
            className="sport-card-gif"
          />
          {item.nom_db && item.nom_db.toLowerCase() !== item.nom.toLowerCase() ? (
            <span className="sport-card-gif-label">Exercice similaire : {item.nom_db}</span>
          ) : null}
        </div>
      ) : null}
      <RecommendationCard
        eyebrow="Exercice"
        title={item.nom}
        description={`${item.justification} Niveau adapte: ${item.niveau_adapte}.`}
        score={item.score_pertinence}
        safetyScore={item.score_securite}
        confidenceScore={Math.round((item.score_pertinence + item.score_securite) / 2)}
        metrics={[
          { label: "Duree", value: item.duree_min, suffix: " min" },
          { label: "Calories", value: item.calories_brulees ?? 0, suffix: " kcal" }
        ]}
        details={[
          { label: "Series et repetitions", value: item.series ? `${item.series} x ${item.repetitions || "repetitions adaptees"}` : item.repetitions },
          { label: "Repos", value: item.repos },
          { label: "Materiel", value: listText(item.equipement_necessaire) || "sans materiel specifique" },
          { label: "Muscles cibles", value: listText(item.muscles_cibles) },
          { label: "Adaptations", value: listText(item.adaptations) || "Ajuste au niveau declare" },
          { label: "Contre-indications", value: listText(item.contre_indications) || "Aucune contre-indication bloquante" }
        ]}
        badges={[item.intensite, item.frequence, ...item.equipement_necessaire, ...item.muscles_cibles, ...item.contraintes_respectees]}
        warning={item.contre_indications.join(" ")}
      />
    </div>
  );
}

function ContextItem({ label, value }: { label: string; value: string | number }) {
  return (
    <div>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function mealFormFromProfile(user: User): MealFormState {
  return {
    objectif_principal: user.objectif_principal || "",
    culture_alimentaire: "",
    regime_alimentaire: user.regime_alimentaire || "",
    allergies: joinList(user.allergies),
    preferences_alimentaires: joinList(user.preferences_alimentaires),
    aliments_evites: joinList(user.aliments_evites),
    contraintes_sante: joinList(user.contraintes_sante),
    type_repas: "",
    temps_preparation: "",
    budget: budgetValue(user.budget_alimentaire)
  };
}

function sportFormFromProfile(user: User): SportFormState {
  const equipment = joinList(user.equipements);
  return {
    objectif_principal: user.objectif_principal || "",
    niveau_sportif: sportLevelValue(user.niveau_sportif),
    hasEquipment: Boolean(equipment),
    equipement_disponible: equipment,
    contraintes_sante: joinList(user.contraintes_sante),
    duree_seance_min: user.duree_seance_min == null ? "" : String(user.duree_seance_min),
    lieu: "",
    type_seance: "",
    muscles_cibles: [],
    hasLimitation: false,
    douleur_limitation: ""
  };
}

function buildMealPayload(form: MealFormState): RecommendationRequest {
  return {
    objectif_principal: emptyToUndefined(form.objectif_principal),
    allergies: splitList(form.allergies),
    regime_alimentaire: emptyToNull(form.regime_alimentaire),
    aliments_evites: splitList(form.aliments_evites),
    budget: form.budget || null,
    contraintes_sante: splitList(form.contraintes_sante),
    preferences_alimentaires: splitList(form.preferences_alimentaires),
    culture_alimentaire: emptyToNull(form.culture_alimentaire),
    type_repas: emptyToNull(form.type_repas),
    temps_preparation: emptyToNull(form.temps_preparation),
    max_nutrition: 5,
    max_sport: 1
  };
}

function buildSportPayload(form: SportFormState): RecommendationRequest {
  const limitation = form.hasLimitation ? form.douleur_limitation : "";
  return {
    objectif_principal: emptyToUndefined(form.objectif_principal),
    niveau_sportif: form.niveau_sportif || null,
    equipement_disponible: form.hasEquipment ? splitList(form.equipement_disponible) : [],
    contraintes_sante: uniqueList([...splitList(form.contraintes_sante), ...splitList(limitation)]),
    duree_seance_min: numberOrUndefined(form.duree_seance_min),
    lieu: emptyToNull(form.lieu),
    type_seance: emptyToNull(form.type_seance),
    muscles_cibles: form.type_seance === "musculation" ? form.muscles_cibles : [],
    douleur_limitation: emptyToNull(limitation),
    preferences_sportives: uniqueList([
      form.lieu,
      form.type_seance,
      ...(form.type_seance === "musculation" ? form.muscles_cibles : [])
    ]),
    max_nutrition: 1,
    max_sport: 5
  };
}

function average(values: Array<number | undefined> | undefined) {
  const clean = (values || []).filter((value): value is number => typeof value === "number" && Number.isFinite(value));
  if (!clean.length) return null;
  return Math.round(clean.reduce((sum, value) => sum + value, 0) / clean.length);
}

function formatNullable(value: number | string | null | undefined) {
  if (value === null || value === undefined || value === "") return "N/A";
  return String(value);
}

function numberOrUndefined(value: string) {
  if (!value.trim()) return undefined;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function emptyToUndefined(value: string) {
  const trimmed = value.trim();
  return trimmed || undefined;
}

function emptyToNull(value: string) {
  const trimmed = value.trim();
  return trimmed || null;
}

function budgetValue(value?: string | null): BudgetValue {
  return value === "faible" || value === "moyen" || value === "eleve" ? value : "";
}

function sportLevelValue(value?: string | null): SportLevelValue {
  return value === "debutant" || value === "intermediaire" || value === "avance" ? value : "";
}

function uniqueList(values: string[]) {
  const seen = new Set<string>();
  const unique: string[] = [];
  for (const raw of values) {
    const value = raw.trim();
    const key = value.toLocaleLowerCase();
    if (value && !seen.has(key)) {
      seen.add(key);
      unique.push(value);
    }
  }
  return unique;
}

function listText(values?: string[] | null) {
  return uniqueList(values || []).join(", ");
}

function budgetLabel(value?: string | null) {
  if (!value) return "";
  return value.replace(/^budget\s+/i, "");
}

function extractBudget(values: string[]) {
  const budget = values.find((value) => value.toLocaleLowerCase().startsWith("budget "));
  return budgetLabel(budget);
}
