export type Role = "UTILISATEUR" | "ADMIN" | "SUPER_ADMIN";

export type PaginationMeta = {
  page: number;
  pageSize: number;
  total: number;
  totalPages: number;
  page_size?: number;
  pages?: number;
  total_pages?: number;
};

export type ApiList<T> = {
  data: T[];
  meta?: PaginationMeta;
};

export type ApiErrorPayload = {
  code?: string;
  message?: string;
  details?: unknown;
};

export type User = {
  utilisateur_id: number;
  organisation_id?: number | null;
  nom_utilisateur: string;
  prenom?: string | null;
  nom?: string | null;
  email?: string | null;
  date_naissance?: string | null;
  genre?: string | null;
  age?: number | null;
  taille_cm?: number | null;
  poids_actuel_kg?: number | null;
  imc?: number | null;
  photo_profil_path?: string | null;
  role: Role;
  statut: string;
  cree_le?: string | null;
  modifie_le?: string | null;
  organisation?: { organisation_id: number; nom: string } | null;
  organisation_nom?: string | null;
  photo_profil_url?: string | null;
  photo_profil?: ProgressionPhoto | null;
  niveau_activite?: string | null;
  niveau_sportif?: string | null;
  allergies_json?: string | null;
  allergies?: string[];
  regime_alimentaire?: string | null;
  preferences_alimentaires_json?: string | null;
  preferences_alimentaires?: string[];
  aliments_evites_json?: string | null;
  aliments_evites?: string[];
  budget_alimentaire?: string | null;
  equipements_json?: string | null;
  equipements?: string[];
  contraintes_sante_json?: string | null;
  contraintes_sante?: string[];
  preferences_sportives_json?: string | null;
  preferences_sportives?: string[];
  frequence_seances_hebdo?: number | null;
  duree_seance_min?: number | null;
  duree_sommeil_h?: number | null;
  qualite_sommeil_score?: number | null;
  objectif_principal?: string | null;
  poids_cible_kg?: number | null;
  date_cible?: string | null;
  onboarding_complete?: boolean;
  onboarding_complete_le?: string | null;
};

export type Organisation = {
  organisation_id: number;
  nom: string;
  adresse?: string | null;
  image_path?: string | null;
  image_url?: string | null;
  cree_le?: string | null;
};

export type MeDashboard = {
  utilisateur_id: number;
  dernier_poids_kg?: number | null;
  dernier_imc?: number | null;
  derniere_duree_sommeil_h?: number | null;
  nb_seances?: number;
  nb_plats?: number;
  calories_journal?: number;
  calories_consommees_jour?: number;
  calories_brulees_30j?: number;
  objectif_actif?: Objectif | null;
  derniere_photo?: ProgressionPhoto | null;
  derniers_repas?: Plat[];
  dernieres_seances?: Seance[];
  repartition_repas?: RepartitionRepas[];
  repartition_entrainements?: RepartitionEntrainement[];
};

export type AdminDashboard = {
  nb_utilisateurs?: number;
  nb_aliments?: number;
  nb_executions_etl?: number;
  taux_qualite_moyen?: number;
  controles_bloquants?: number;
};

export type MesureBiometrique = {
  mesure_id: number;
  mesure_le: string;
  poids_kg?: number | null;
  taille_cm?: number | null;
  imc?: number | null;
  taux_masse_grasse?: number | null;
  bpm_repos?: number | null;
  bpm_moyen?: number | null;
  bpm_max?: number | null;
  eau_l?: number | null;
};

export type SommeilSante = {
  mesure_sommeil_id: number;
  mesure_le: string;
  duree_sommeil_h?: number | null;
  qualite_sommeil_score?: number | null;
  activite_physique_min_jour?: number | null;
  stress_score?: number | null;
  frequence_cardiaque_bpm?: number | null;
  pas_jour?: number | null;
  trouble_sommeil_normalise?: string | null;
};

export type Seance = {
  seance_id: number;
  date_seance: string;
  type_entrainement?: string | null;
  duree_seance_min?: number | null;
  calories_brulees_total?: number | null;
  frequence_entrainement_j_sem?: number | null;
  niveau_experience?: string | null;
  eau_l?: number | null;
  commentaire?: string | null;
};

export type JournalAlimentaire = {
  journal_id: number;
  plat_id?: number | null;
  aliment_id?: number | null;
  consomme_le: string;
  type_repas?: string | null;
  aliment_nom_libre?: string | null;
  quantite?: number | null;
  unite_quantite?: string | null;
  calories_kcal?: number | null;
  eau_ml?: number | null;
};

export type Objectif = {
  objectif_id: number;
  type_objectif: string;
  poids_cible_kg?: number | null;
  statut_objectif?: string | null;
  date_debut?: string | null;
  date_fin?: string | null;
  actif_unique?: boolean | null;
  commentaire?: string | null;
};

export type Plat = {
  plat_id: number;
  utilisateur_id?: number;
  consomme_le?: string | null;
  type_repas?: string | null;
  nom_plat?: string | null;
  calories_totales_kcal?: number | null;
  somme_lignes_kcal?: number | null;
  coherence_calories?: boolean | null;
};

export type AlimentResume = {
  aliment_id: number;
  nom: string;
  categorie?: string | null;
  calories_kcal?: number | null;
  proteines_g?: number | null;
  glucides_g?: number | null;
  lipides_g?: number | null;
};

export type PlatLigne = JournalAlimentaire & {
  aliment?: AlimentResume | null;
};

export type ProgressionPhoto = {
  photo_id: number;
  utilisateur_id?: number;
  objectif_id?: number | null;
  type_photo?: string | null;
  image_path?: string | null;
  image_url?: string | null;
  photo_url?: string | null;
  url?: string | null;
  prise_le?: string | null;
  commentaire?: string | null;
  objectif?: Objectif | null;
};

export type ExerciceResume = {
  exercice_id: number;
  nom: string;
  body_part_principale?: string | null;
  muscle_cible_principal?: string | null;
  equipement_principal?: string | null;
  gif_180_path?: string | null;
  gif_360_path?: string | null;
  gif_720_path?: string | null;
  gif_1080_path?: string | null;
  gif_180_url?: string | null;
  gif_360_url?: string | null;
  gif_720_url?: string | null;
  gif_1080_url?: string | null;
};

export type Exercice = ExerciceResume & {
  source_id?: number | null;
  external_id?: string | null;
  body_parts_json?: string | null;
  target_muscles_json?: string | null;
  secondary_muscles_json?: string | null;
  equipments_json?: string | null;
  instructions_json?: string | null;
};

export type ExerciceFilters = {
  body_parts: string[];
  target_muscles: string[];
  equipements: string[];
};

export type SeancesFilters = {
  types_entrainement: string[];
  niveaux_experience: string[];
};

export type Aliment = {
  aliment_id: number;
  nom: string;
  categorie?: string | null;
  calories_kcal?: number | null;
  proteines_g?: number | null;
  glucides_g?: number | null;
  lipides_g?: number | null;
  fibres_g?: number | null;
  sucres_g?: number | null;
  sodium_mg?: number | null;
  cholesterol_mg?: number | null;
};

export type SeanceExercice = {
  seance_exercice_id: number;
  ordre_exercice?: number | null;
  series_nb?: number | null;
  repetitions_nb?: number | null;
  charge_kg?: number | null;
  duree_min?: number | null;
  calories_brulees_estimees?: number | null;
  commentaire?: string | null;
  exercice: ExerciceResume;
};

export type UserKpis = {
  poids_kg?: number | null;
  imc?: number | null;
  duree_sommeil_h?: number | null;
  seances_30j: number;
  calories_brulees_30j: number;
  calories_consommees_jour: number;
  objectif_actif?: Objectif | null;
  photos_total?: number;
  plats_30j?: number;
};

export type RepartitionRepas = {
  type_repas: string;
  nb: number;
  calories?: number;
};

export type RepartitionEntrainement = {
  type: string;
  nb: number;
};

export type NutritionCharts = {
  granularity: string;
  calories_par_bucket: Array<{ bucket: string; calories: number; nb_lignes: number }>;
  top_aliments: Array<{ aliment_id: number; nom: string; nb: number; calories: number }>;
  repartition_repas: RepartitionRepas[];
};

export type MealAnalysisFood = {
  nom: string;
  label_source: string;
  confidence?: number | null;
  matched_aliment_id?: number | null;
  matched_aliment_nom?: string | null;
  portion_estimee?: string | null;
  calories_kcal?: number | null;
  proteines_g?: number | null;
  glucides_g?: number | null;
  lipides_g?: number | null;
  fibres_g?: number | null;
  sucres_g?: number | null;
  sodium_mg?: number | null;
  cholesterol_mg?: number | null;
  details?: string | null;
};

export type MealAnalysisPortion = {
  nom: string;
  portion: string;
  grammes_estimes?: number | null;
};

export type MealAnalysisMacros = {
  proteines_g?: number | null;
  glucides_g?: number | null;
  lipides_g?: number | null;
};

export type MealVisionPrediction = {
  label: string;
  score: number;
};

export type MealAnalysisConfig = {
  external_ai_enabled: boolean;
  force_mock: boolean;
  huggingface_configured: boolean;
  deepseek_configured?: boolean;
  vision_model: string;
  vision_fallback_models?: string[];
  provider?: string;
};

export type MealAnalysisResult = {
  source_analyse: "huggingface" | "huggingface_plus_local_reasoning" | "local_mock" | "gemini-2.5-flash";
  mode: "external" | "mock";
  plat_detecte: string;
  confidence: number;
  aliments_detectes: MealAnalysisFood[];
  portions_estimees: MealAnalysisPortion[];
  calories_estimees?: number | null;
  macronutriments: MealAnalysisMacros;
  hypotheses: string[];
  commentaire: string;
  limites_estimation: string[];
  raw_vision_predictions: MealVisionPrediction[];
};

export type RecommendationRequest = {
  objectif_principal?: string | null;
  allergies?: string[];
  regime_alimentaire?: string | null;
  aliments_evites?: string[];
  budget?: "faible" | "moyen" | "eleve" | null;
  niveau_sportif?: "debutant" | "intermediaire" | "avance" | null;
  niveau_activite?: string | null;
  equipement_disponible?: string[];
  contraintes_sante?: string[];
  preferences_alimentaires?: string[];
  preferences_sportives?: string[];
  culture_alimentaire?: string | null;
  type_repas?: string | null;
  temps_preparation?: string | null;
  lieu?: string | null;
  type_seance?: string | null;
  muscles_cibles?: string[];
  douleur_limitation?: string | null;
  frequence_seances_hebdo?: number | null;
  duree_seance_min?: number | null;
  max_nutrition?: number;
  max_sport?: number;
};

export type RecommendationContext = {
  utilisateur_id: number;
  age?: number | null;
  sexe?: string | null;
  taille_cm?: number | null;
  poids_kg?: number | null;
  imc?: number | null;
  objectif_principal: string;
  budget?: string | null;
  niveau_sportif: string;
  niveau_activite?: string | null;
  frequence_seances_hebdo?: number | null;
  duree_seance_min?: number | null;
  donnees_utilisees: string[];
};

export type NutritionRecommendation = {
  aliment_id?: number | null;
  source: string;
  type: "plat" | "recette" | "aliment";
  nom: string;
  recette: string;
  calories_estimees?: number | null;
  proteines_g?: number | null;
  glucides_g?: number | null;
  lipides_g?: number | null;
  score_nutritionnel: number;
  score_pertinence: number;
  score_securite: number;
  justification: string;
  ingredients?: string[];
  preparation?: string | null;
  budget_estime?: string | null;
  allergenes_exclus?: string[];
  contraintes_respectees: string[];
  alternatives: string[];
  badges: string[];
};

export type SportExerciseRecommendation = {
  exercice_id: number;
  nom: string;
  duree_min: number;
  intensite: string;
  frequence: string;
  equipement_necessaire: string[];
  muscles_cibles: string[];
  niveau_adapte: string;
  score_pertinence: number;
  score_securite: number;
  justification: string;
  series?: number | null;
  repetitions?: string | null;
  repos?: string | null;
  adaptations?: string[];
  contre_indications: string[];
  contraintes_respectees: string[];
  gif_url?: string | null;
  nom_db?: string | null;
  exercice_id_db?: number | null;
  calories_brulees?: number | null;
};

export type SportSessionRecommendation = {
  nom: string;
  duree_min: number;
  intensite: string;
  frequence: string;
  exercices: SportExerciseRecommendation[];
  materiel_necessaire?: string[];
  muscles_cibles?: string[];
  contre_indications?: string[];
  justification: string;
};

export type RecommendationResponse = {
  generated_at: string;
  source: "local_rules" | "external_ai";
  fallback_utilise: boolean;
  fallback_message?: string | null;
  contexte: RecommendationContext;
  contraintes_prises_en_compte: string[];
  nutrition: NutritionRecommendation[];
  sport: {
    exercices: SportExerciseRecommendation[];
    seances: SportSessionRecommendation[];
  };
  messages: string[];
};

export type ExecutionEtl = {
  execution_id: number;
  source_id: number;
  statut: string;
  demarre_le?: string | null;
  termine_le?: string | null;
  lignes_lues?: number | null;
  lignes_valides?: number | null;
  lignes_invalides?: number | null;
  nb_rejets?: number | null;
  taux_qualite?: number | null;
  message?: string | null;
};

export type LotDonnees = {
  lot_id: number;
  execution_id?: number | null;
  source_id?: number | null;
  nom_lot?: string | null;
  statut?: string | null;
  cree_par_utilisateur_id?: number | null;
  valide_par_utilisateur_id?: number | null;
  valide_le?: string | null;
  commentaire_validation?: string | null;
  cree_le?: string | null;
};

export type AdminQualityKpis = {
  nb_total: number;
  nb_bloquants: number;
  nb_rejets: number;
  ratio_bloquants: number;
  ratio_rejets: number;
  nb_entites_distinctes: number;
};

export type RegleQualite = {
  regle_id: number;
  entite: string;
  nom_champ?: string | null;
  code_regle: string;
  type_regle?: string | null;
  severite?: string | null;
  description?: string | null;
  actif: boolean;
};

export type SourceDonnees = {
  source_id: number;
  nom: string;
  description?: string | null;
  type_source?: string | null;
  format_source?: string | null;
  actif: boolean;
  cree_le?: string | null;
};

export type SuperAdminDashboard = {
  nb_utilisateurs?: number;
  nb_admins?: number;
  nb_executions_etl?: number;
  qualite_min?: number;
  qualite_max?: number;
};

export type FailedExecution = {
  execution_id: number;
  source_id?: number | null;
  statut: string;
  taux_qualite?: number | null;
  nb_rejets?: number | null;
  termine_le?: string | null;
  message?: string | null;
};

export type BlockedLot = {
  lot_id: number;
  nom_lot?: string | null;
  statut?: string | null;
  cree_le?: string | null;
  nb_bloquants?: number | null;
};

export type ControleQualite = {
  controle_id: number;
  execution_id: number;
  lot_id?: number | null;
  regle_id?: number | null;
  entite: string;
  ref_externe?: string | null;
  ref_ligne?: string | null;
  nom_champ?: string | null;
  valeur_observee?: string | null;
  valeur_corrigee?: string | null;
  niveau?: string | null;
  type_controle?: string | null;
  decision_finale?: string | null;
  est_bloquant?: boolean | null;
  code_controle?: string | null;
  description?: string | null;
  cree_le?: string | null;
};

export type QualityFilterOptions = {
  niveaux: string[];
  decisions: string[];
  entites: string[];
  sources: Array<{ id: number; nom: string }>;
  lots: Array<{ id: number; nom: string }>;
};

export type EtlCompareChange = {
  lot: { id: number; nom: string };
  source: { id: number; nom: string };
  entite: string;
  ref_externe?: string | null;
  raw?: { id?: number; payload_json?: unknown } | null;
  staging?: {
    id?: number;
    payload_normalise_json?: unknown;
    source_payload_json?: unknown;
    statut_validation?: string | null;
    code_rejet_potentiel?: string | null;
    est_parseable?: boolean | null;
  } | null;
  quality_controls: ControleQualite[];
  has_changes: boolean;
};
