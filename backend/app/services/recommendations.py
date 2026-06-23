from __future__ import annotations

import json
import re
import unicodedata
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    Aliment,
    Exercice,
    JournalAlimentaire,
    MesureBiometrique,
    MesureSommeilSante,
    ObjectifUtilisateur,
    SeanceEntrainement,
    SeanceExercice,
    Utilisateur,
)
from app.schemas.recommendations import (
    NutritionRecommendation,
    RecommendationContext,
    RecommendationRequest,
    RecommendationResponse,
    SportExerciseRecommendation,
    SportRecommendations,
    SportSessionRecommendation,
)


ALLERGEN_ALIASES: dict[str, tuple[str, ...]] = {
    "arachide": ("arachide", "cacahuete", "cacahuete", "peanut", "peanuts"),
    "cacahuete": ("arachide", "cacahuete", "peanut", "peanuts"),
    "fruits_a_coque": ("amande", "noix", "noisette", "pistache", "cajou", "pecan", "nut", "nuts"),
    "lactose": ("lactose", "lait", "fromage", "yaourt", "beurre", "creme", "milk", "cheese", "yogurt"),
    "gluten": ("gluten", "ble", "farine", "pain", "pates", "pasta", "semoule", "couscous", "pizza"),
    "oeuf": ("oeuf", "oeufs", "egg", "eggs", "omelette"),
    "poisson": ("poisson", "fish", "thon", "saumon", "cabillaud"),
    "crustaces": ("crevette", "crabe", "homard", "shrimp", "crab", "lobster"),
    "soja": ("soja", "soy", "tofu"),
    "sesame": ("sesame",),
}

REGIME_BLOCKERS: dict[str, tuple[str, ...]] = {
    "vegetarien": ("poulet", "boeuf", "porc", "jambon", "bacon", "viande", "dinde", "thon", "saumon", "poisson", "fish", "chicken", "beef"),
    "vegetalien": ("poulet", "boeuf", "porc", "jambon", "bacon", "viande", "dinde", "thon", "saumon", "poisson", "oeuf", "lait", "fromage", "yaourt", "miel"),
    "vegan": ("poulet", "boeuf", "porc", "jambon", "bacon", "viande", "dinde", "thon", "saumon", "poisson", "oeuf", "lait", "fromage", "yaourt", "miel"),
    "sans_gluten": ALLERGEN_ALIASES["gluten"],
    "halal": ("porc", "jambon", "bacon", "saucisson", "pork", "ham"),
}

EXPENSIVE_FOOD_TERMS = (
    "saumon",
    "sushi",
    "boeuf",
    "steak",
    "crevette",
    "avocat",
    "noix",
    "amande",
)

NO_EQUIPMENT_TERMS = {
    "",
    "none",
    "no equipment",
    "body weight",
    "bodyweight",
    "poids du corps",
    "sans equipement",
    "sans materiel",
    "body only",
}

EQUIPMENT_ALIASES: dict[str, tuple[str, ...]] = {
    "bodyweight": tuple(NO_EQUIPMENT_TERMS),
    "dumbbell": ("dumbbell", "dumbbells", "haltere", "halteres"),
    "barbell": ("barbell", "barre"),
    "kettlebell": ("kettlebell",),
    "band": ("band", "resistance band", "elastique", "bande"),
    "cable": ("cable", "cables"),
    "machine": ("machine", "machines", "smith machine"),
    "bench": ("bench", "banc"),
    "ball": ("ball", "medicine ball", "stability ball", "swiss ball", "ballon"),
    "pullup_bar": ("pull-up bar", "pull up bar", "barre de traction"),
    "rope": ("rope", "corde"),
    "mat": ("mat", "tapis"),
    "gym": ("gym", "salle", "salle de sport", "tout equipement"),
}


class RecommendationEngine:
    """Moteur local explicable, sans appel externe ni cle API."""

    def build(
        self,
        db: Session,
        user: Utilisateur,
        request: RecommendationRequest,
    ) -> RecommendationResponse:
        request = self._request_with_user_defaults(user, request)
        latest_bio = self._latest_biometrie(db, user.utilisateur_id)
        latest_sleep = self._latest_sommeil(db, user.utilisateur_id)
        active_objective = self._active_objective(db, user.utilisateur_id)
        latest_training_level = self._latest_training_level(db, user.utilisateur_id)

        age = self._age_from_birthdate(user.date_naissance)
        if age is None:
            age = latest_bio.age_source if latest_bio and latest_bio.age_source else None
        if age is None:
            age = latest_sleep.age_source if latest_sleep and latest_sleep.age_source else None

        height = user.taille_cm or (latest_bio.taille_cm if latest_bio else None)
        weight = latest_bio.poids_kg if latest_bio else None
        imc = latest_bio.imc if latest_bio else None
        if imc is None and weight and height:
            height_m = float(height) / 100
            imc = round(float(weight) / (height_m * height_m), 2) if height_m else None

        objective_label = request.objectif_principal or (active_objective.type_objectif if active_objective else None) or "sante"
        goal = self._goal_key(objective_label)
        sport_level = self._sport_level(request.niveau_sportif or latest_training_level)
        used_data = ["profil utilisateur", "catalogue aliments", "catalogue exercices"]
        if latest_bio:
            used_data.append("derniere biometrie")
        if latest_sleep:
            used_data.append("dernieres donnees sommeil/sante")
        if active_objective:
            used_data.append("objectif actif")
        if self._has_food_history(db, user.utilisateur_id):
            used_data.append("historique repas")
        if self._has_sport_history(db, user.utilisateur_id):
            used_data.append("historique exercices")

        context = RecommendationContext(
            utilisateur_id=user.utilisateur_id,
            age=age,
            sexe=user.genre or (latest_bio.genre_source if latest_bio else None) or (latest_sleep.genre_source if latest_sleep else None),
            taille_cm=height,
            poids_kg=weight,
            imc=imc,
            objectif_principal=goal,
            budget=request.budget,
            niveau_sportif=sport_level,
            niveau_activite=request.niveau_activite,
            frequence_seances_hebdo=request.frequence_seances_hebdo,
            duree_seance_min=request.duree_seance_min,
            donnees_utilisees=used_data,
        )

        nutrition, nutrition_messages = self._nutrition_recommendations(db, user.utilisateur_id, request, goal)
        sport, sport_messages = self._sport_recommendations(db, user.utilisateur_id, request, goal, sport_level)

        messages = [
            "Moteur local utilise: aucune cle API externe n'est requise pour ces recommandations.",
            *nutrition_messages,
            *sport_messages,
        ]

        return RecommendationResponse(
            generated_at=datetime.utcnow(),
            source="local_rules",
            fallback_utilise=True,
            fallback_message="Fallback local regles metier utilise pour garantir une reponse sans IA externe.",
            contexte=context,
            contraintes_prises_en_compte=self._constraints_summary(request),
            nutrition=nutrition,
            sport=sport,
            messages=[message for message in messages if message],
        )

    def food_block_reasons(
        self,
        name: str,
        category: str | None,
        allergies: list[str],
        regime: str | None,
    ) -> list[str]:
        text = self._normalize(f"{name} {category or ''}")
        reasons: list[str] = []
        for allergy in allergies:
            allergy_key = self._normalize(allergy).replace(" ", "_")
            aliases = ALLERGEN_ALIASES.get(allergy_key) or (self._normalize(allergy),)
            if any(alias and self._normalize(alias) in text for alias in aliases):
                reasons.append(f"allergie ou aliment evite: {allergy}")

        if regime:
            regime_key = self._normalize(regime).replace(" ", "_").replace("-", "_")
            blockers = REGIME_BLOCKERS.get(regime_key, ())
            if any(self._normalize(term) in text for term in blockers):
                reasons.append(f"regime incompatible: {regime}")

        return reasons

    def equipment_is_allowed(self, needed: list[str], available: list[str]) -> bool:
        needed_keys = self._canonical_equipment(needed)
        needed_keys.discard("bodyweight")
        if not needed_keys:
            return True

        available_keys = self._canonical_equipment(available)
        if "gym" in available_keys:
            return True
        return needed_keys.issubset(available_keys)

    def _nutrition_recommendations(
        self,
        db: Session,
        utilisateur_id: int,
        request: RecommendationRequest,
        goal: str,
    ) -> tuple[list[NutritionRecommendation], list[str]]:
        rows = db.execute(
            select(Aliment)
            .order_by(Aliment.aliment_id.asc())
            .limit(600)
        ).scalars().all()
        if not rows:
            return [], ["Aucun aliment ETL/catalogue disponible pour generer des recommandations nutrition."]

        history = self._food_history(db, utilisateur_id)
        recommendations: list[NutritionRecommendation] = []
        blocked_allergy = 0
        blocked_budget = 0
        food_preferences = self._unique_strings([
            *request.preferences_alimentaires,
            request.culture_alimentaire or "",
            request.type_repas or "",
            request.temps_preparation or "",
        ])

        for aliment in rows:
            reasons = self.food_block_reasons(
                aliment.nom,
                aliment.categorie,
                [*request.allergies, *request.aliments_evites],
                request.regime_alimentaire,
            )
            if reasons:
                blocked_allergy += 1
                continue

            budget_level = self._food_budget_level(aliment)
            if request.budget == "faible" and budget_level == "eleve":
                blocked_budget += 1
                continue

            nutrition_score = self._nutrition_score(aliment, goal)
            safety_score = self._nutrition_safety_score(aliment, request)
            preference_bonus = self._preference_bonus(aliment.nom, aliment.categorie, food_preferences)
            history_bonus = 4 if self._normalize(aliment.nom) in history else 0
            budget_bonus = 4 if request.budget and budget_level == request.budget else 0
            time_bonus = 3 if request.temps_preparation == "rapide" else 0
            relevance = self._clamp(nutrition_score + preference_bonus + history_bonus + budget_bonus + time_bonus)

            badges = [goal, f"budget {budget_level}"]
            if self._safe_float(aliment.proteines_g) >= 12:
                badges.append("proteines")
            if request.regime_alimentaire:
                badges.append(request.regime_alimentaire)
            if request.culture_alimentaire:
                badges.append(request.culture_alimentaire)
            if request.type_repas:
                badges.append(request.type_repas.replace("_", " "))
            if request.temps_preparation:
                badges.append(request.temps_preparation.replace("_", " "))

            constraints = []
            if request.allergies:
                constraints.append("allergies exclues")
            if request.regime_alimentaire:
                constraints.append(f"regime {request.regime_alimentaire}")
            if request.budget:
                constraints.append(f"budget {request.budget}")
            if request.culture_alimentaire:
                constraints.append(f"culture alimentaire {request.culture_alimentaire}")
            if request.temps_preparation:
                constraints.append(f"temps {request.temps_preparation.replace('_', ' ')}")

            recipe_hint = self._recipe_hint(aliment, goal)
            recommendations.append(
                NutritionRecommendation(
                    aliment_id=aliment.aliment_id,
                    source="aliment",
                    type="recette",
                    nom=aliment.nom,
                    recette=recipe_hint,
                    calories_estimees=self._rounded(aliment.calories_kcal),
                    proteines_g=self._rounded(aliment.proteines_g),
                    glucides_g=self._rounded(aliment.glucides_g),
                    lipides_g=self._rounded(aliment.lipides_g),
                    score_nutritionnel=nutrition_score,
                    score_pertinence=relevance,
                    score_securite=safety_score,
                    justification=self._nutrition_justification(aliment, goal, request),
                    ingredients=self._nutrition_ingredients(aliment),
                    preparation=recipe_hint,
                    budget_estime=budget_level,
                    allergenes_exclus=self._unique_strings([*request.allergies, *request.aliments_evites]),
                    contraintes_respectees=constraints,
                    alternatives=[],
                    badges=badges,
                )
            )

        recommendations.sort(key=lambda item: (item.score_securite, item.score_pertinence, item.score_nutritionnel), reverse=True)
        selected = recommendations[: request.max_nutrition]
        selected_names = [item.nom for item in selected]
        for item in selected:
            item.alternatives = [name for name in selected_names if name != item.nom][:2]

        messages: list[str] = []
        if blocked_allergy:
            messages.append(f"{blocked_allergy} aliment(s) exclus pour allergie ou regime incompatible.")
        if blocked_budget:
            messages.append(f"{blocked_budget} aliment(s) exclus car le budget faible etait incompatible.")
        if not selected:
            messages.append("Aucune recommandation nutrition compatible avec toutes les contraintes.")
        return selected, messages

    def _sport_recommendations(
        self,
        db: Session,
        utilisateur_id: int,
        request: RecommendationRequest,
        goal: str,
        sport_level: str,
    ) -> tuple[SportRecommendations, list[str]]:
        rows = db.execute(
            select(Exercice)
            .order_by(Exercice.exercice_id.asc())
            .limit(700)
        ).scalars().all()
        if not rows:
            return SportRecommendations(), ["Aucun exercice ETL/catalogue disponible pour generer des recommandations sport."]

        history_ids = self._exercise_history_ids(db, utilisateur_id)
        exercises: list[SportExerciseRecommendation] = []
        blocked_equipment = 0
        blocked_health = 0
        health_constraints = self._unique_strings([
            *request.contraintes_sante,
            request.douleur_limitation or "",
        ])
        sport_preferences = self._unique_strings([
            *request.preferences_sportives,
            request.lieu or "",
            request.type_seance or "",
            *request.muscles_cibles,
        ])

        for exercice in rows:
            needed = self._exercise_equipment(exercice)
            if not self.equipment_is_allowed(needed, request.equipement_disponible):
                blocked_equipment += 1
                continue

            contraindications = self._exercise_contraindications(exercice, health_constraints)
            if self._has_severe_contraindication(contraindications):
                blocked_health += 1
                continue

            safety_score = self._clamp(100 - len(contraindications) * 18)
            preference_bonus = self._preference_bonus(
                exercice.nom,
                " ".join(self._exercise_muscles(exercice)),
                sport_preferences,
            )
            history_bonus = 4 if exercice.exercice_id in history_ids else 0
            goal_bonus = self._exercise_goal_bonus(exercice, goal)
            level_bonus = self._exercise_level_bonus(exercice, sport_level)
            muscle_bonus = self._requested_muscle_bonus(exercice, request.muscles_cibles)
            session_bonus = self._session_type_bonus(exercice, request.type_seance)
            relevance = self._clamp(58 + preference_bonus + history_bonus + goal_bonus + level_bonus + muscle_bonus + session_bonus)
            duration = self._exercise_duration(sport_level, request.duree_seance_min)
            intensity = self._sport_intensity(sport_level, health_constraints)
            frequency = self._sport_frequency(sport_level, goal, request.frequence_seances_hebdo)
            muscles = self._exercise_muscles(exercice)

            constraints = []
            if request.equipement_disponible:
                constraints.append("equipement disponible respecte")
            else:
                constraints.append("sans materiel requis")
            if health_constraints:
                constraints.append("contraintes sante analysees")
            if request.lieu:
                constraints.append(f"lieu {request.lieu.replace('_', ' ')}")
            if request.type_seance:
                constraints.append(f"type {request.type_seance.replace('_', ' ')}")
            if request.muscles_cibles:
                constraints.append("muscles demandes: " + ", ".join(request.muscles_cibles))

            exercises.append(
                SportExerciseRecommendation(
                    exercice_id=exercice.exercice_id,
                    nom=exercice.nom,
                    duree_min=duration,
                    intensite=intensity,
                    frequence=frequency,
                    equipement_necessaire=[item for item in needed if item],
                    muscles_cibles=muscles[:5],
                    niveau_adapte=sport_level,
                    score_pertinence=relevance,
                    score_securite=safety_score,
                    justification=self._exercise_justification(exercice, goal, sport_level),
                    series=self._exercise_sets(sport_level),
                    repetitions=self._exercise_repetitions(sport_level, intensity),
                    repos=self._exercise_rest(intensity),
                    adaptations=self._exercise_adaptations(sport_level, health_constraints),
                    contre_indications=contraindications,
                    contraintes_respectees=constraints,
                )
            )

        exercises.sort(key=lambda item: (item.score_securite, item.score_pertinence), reverse=True)
        selected = exercises[: request.max_sport]
        sessions: list[SportSessionRecommendation] = []
        if selected:
            session_items = selected[: min(4, len(selected))]
            sessions.append(
                SportSessionRecommendation(
                    nom=f"Seance {goal.replace('_', ' ')}",
                    duree_min=sum(item.duree_min for item in session_items),
                    intensite=self._sport_intensity(sport_level, health_constraints),
                    frequence=self._sport_frequency(sport_level, goal, request.frequence_seances_hebdo),
                    exercices=session_items,
                    materiel_necessaire=self._unique_strings(
                        equipment for item in session_items for equipment in item.equipement_necessaire
                    ),
                    muscles_cibles=self._unique_strings(
                        muscle for item in session_items for muscle in item.muscles_cibles
                    )[:8],
                    contre_indications=self._unique_strings(
                        warning for item in session_items for warning in item.contre_indications
                    ),
                    justification="Seance composee uniquement d'exercices compatibles avec l'equipement declare et les contraintes sante.",
                )
            )

        messages: list[str] = []
        if blocked_equipment:
            messages.append(f"{blocked_equipment} exercice(s) exclus car le materiel requis n'etait pas disponible.")
        if blocked_health:
            messages.append(f"{blocked_health} exercice(s) exclus par securite selon les contraintes sante.")
        if not selected:
            messages.append("Aucune recommandation sport compatible avec toutes les contraintes.")

        return SportRecommendations(exercices=selected, seances=sessions), messages

    def _latest_biometrie(self, db: Session, utilisateur_id: int) -> MesureBiometrique | None:
        return db.execute(
            select(MesureBiometrique)
            .where(MesureBiometrique.utilisateur_id == utilisateur_id)
            .order_by(MesureBiometrique.mesure_le.desc())
            .limit(1)
        ).scalar_one_or_none()

    def _latest_sommeil(self, db: Session, utilisateur_id: int) -> MesureSommeilSante | None:
        return db.execute(
            select(MesureSommeilSante)
            .where(MesureSommeilSante.utilisateur_id == utilisateur_id)
            .order_by(MesureSommeilSante.mesure_le.desc())
            .limit(1)
        ).scalar_one_or_none()

    def _active_objective(self, db: Session, utilisateur_id: int) -> ObjectifUtilisateur | None:
        return db.execute(
            select(ObjectifUtilisateur)
            .where(
                ObjectifUtilisateur.utilisateur_id == utilisateur_id,
                ObjectifUtilisateur.actif_unique.is_(True),
            )
            .order_by(ObjectifUtilisateur.objectif_id.desc())
            .limit(1)
        ).scalar_one_or_none()

    def _latest_training_level(self, db: Session, utilisateur_id: int) -> str | None:
        return db.scalar(
            select(SeanceEntrainement.niveau_experience)
            .where(
                SeanceEntrainement.utilisateur_id == utilisateur_id,
                SeanceEntrainement.niveau_experience.is_not(None),
            )
            .order_by(SeanceEntrainement.date_seance.desc())
            .limit(1)
        )

    def _has_food_history(self, db: Session, utilisateur_id: int) -> bool:
        return bool(
            db.scalar(
                select(func.count(JournalAlimentaire.journal_id)).where(
                    JournalAlimentaire.utilisateur_id == utilisateur_id
                )
            )
        )

    def _has_sport_history(self, db: Session, utilisateur_id: int) -> bool:
        return bool(
            db.scalar(
                select(func.count(SeanceEntrainement.seance_id)).where(
                    SeanceEntrainement.utilisateur_id == utilisateur_id
                )
            )
        )

    def _food_history(self, db: Session, utilisateur_id: int) -> set[str]:
        since = datetime.utcnow() - timedelta(days=45)
        rows = db.execute(
            select(Aliment.nom)
            .join(JournalAlimentaire, JournalAlimentaire.aliment_id == Aliment.aliment_id)
            .where(
                JournalAlimentaire.utilisateur_id == utilisateur_id,
                JournalAlimentaire.consomme_le >= since,
            )
            .limit(80)
        ).all()
        return {self._normalize(row[0]) for row in rows if row[0]}

    def _exercise_history_ids(self, db: Session, utilisateur_id: int) -> set[int]:
        since = datetime.utcnow() - timedelta(days=60)
        rows = db.execute(
            select(SeanceExercice.exercice_id)
            .join(SeanceEntrainement, SeanceEntrainement.seance_id == SeanceExercice.seance_id)
            .where(
                SeanceEntrainement.utilisateur_id == utilisateur_id,
                SeanceEntrainement.date_seance >= since,
            )
            .limit(120)
        ).all()
        return {int(row[0]) for row in rows if row[0]}

    def _constraints_summary(self, request: RecommendationRequest) -> list[str]:
        constraints: list[str] = []
        if request.allergies:
            constraints.append("allergies: " + ", ".join(request.allergies))
        if request.regime_alimentaire:
            constraints.append(f"regime: {request.regime_alimentaire}")
        if request.budget:
            constraints.append(f"budget: {request.budget}")
        if request.culture_alimentaire:
            constraints.append(f"culture alimentaire: {request.culture_alimentaire}")
        if request.type_repas:
            constraints.append(f"type repas: {request.type_repas.replace('_', ' ')}")
        if request.temps_preparation:
            constraints.append(f"temps preparation: {request.temps_preparation.replace('_', ' ')}")
        if request.equipement_disponible:
            constraints.append("equipement: " + ", ".join(request.equipement_disponible))
        else:
            constraints.append("equipement: sans materiel uniquement")
        if request.lieu:
            constraints.append(f"lieu: {request.lieu.replace('_', ' ')}")
        if request.type_seance:
            constraints.append(f"type seance: {request.type_seance.replace('_', ' ')}")
        if request.muscles_cibles:
            constraints.append("muscles cibles: " + ", ".join(request.muscles_cibles))
        if request.niveau_activite:
            constraints.append(f"niveau activite: {request.niveau_activite}")
        if request.frequence_seances_hebdo is not None:
            constraints.append(f"frequence souhaitee: {request.frequence_seances_hebdo}/semaine")
        if request.duree_seance_min is not None:
            constraints.append(f"duree seance souhaitee: {request.duree_seance_min} min")
        if request.contraintes_sante:
            constraints.append("contraintes sante: " + ", ".join(request.contraintes_sante))
        if request.douleur_limitation:
            constraints.append(f"douleur limitation: {request.douleur_limitation}")
        if request.preferences_alimentaires:
            constraints.append("preferences alimentaires: " + ", ".join(request.preferences_alimentaires))
        if request.aliments_evites:
            constraints.append("aliments evites: " + ", ".join(request.aliments_evites))
        if request.preferences_sportives:
            constraints.append("preferences sportives: " + ", ".join(request.preferences_sportives))
        return constraints

    def _request_with_user_defaults(self, user: Utilisateur, request: RecommendationRequest) -> RecommendationRequest:
        update: dict[str, Any] = {}
        provided = request.model_fields_set
        if "allergies" not in provided and not request.allergies:
            update["allergies"] = self._json_list(user.allergies_json)
        if "aliments_evites" not in provided and not request.aliments_evites:
            update["aliments_evites"] = self._json_list(user.aliments_evites_json)
        if "regime_alimentaire" not in provided and not request.regime_alimentaire and user.regime_alimentaire:
            update["regime_alimentaire"] = user.regime_alimentaire
        if "preferences_alimentaires" not in provided and not request.preferences_alimentaires:
            update["preferences_alimentaires"] = self._json_list(user.preferences_alimentaires_json)
        if "preferences_sportives" not in provided and not request.preferences_sportives:
            update["preferences_sportives"] = self._json_list(user.preferences_sportives_json)
        if "equipement_disponible" not in provided and not request.equipement_disponible:
            update["equipement_disponible"] = self._json_list(user.equipements_json)
        if "contraintes_sante" not in provided and not request.contraintes_sante:
            update["contraintes_sante"] = self._json_list(user.contraintes_sante_json)
        if "budget" not in provided and request.budget is None and user.budget_alimentaire in {"faible", "moyen", "eleve"}:
            update["budget"] = user.budget_alimentaire
        if "niveau_sportif" not in provided and request.niveau_sportif is None and user.niveau_sportif in {"debutant", "intermediaire", "avance"}:
            update["niveau_sportif"] = user.niveau_sportif
        if "niveau_activite" not in provided and request.niveau_activite is None and user.niveau_activite:
            update["niveau_activite"] = user.niveau_activite
        if "frequence_seances_hebdo" not in provided and request.frequence_seances_hebdo is None and user.frequence_seances_hebdo is not None:
            update["frequence_seances_hebdo"] = user.frequence_seances_hebdo
        if "duree_seance_min" not in provided and request.duree_seance_min is None and user.duree_seance_min is not None:
            update["duree_seance_min"] = user.duree_seance_min
        return request.model_copy(update=update) if update else request

    def _nutrition_score(self, aliment: Aliment, goal: str) -> int:
        calories = self._safe_float(aliment.calories_kcal)
        protein = self._safe_float(aliment.proteines_g)
        carbs = self._safe_float(aliment.glucides_g)
        fat = self._safe_float(aliment.lipides_g)
        fiber = self._safe_float(aliment.fibres_g)
        sugar = self._safe_float(aliment.sucres_g)
        sodium = self._safe_float(aliment.sodium_mg)

        score = 52
        if goal == "perte_poids":
            if 80 <= calories <= 260:
                score += 16
            if protein >= 10:
                score += 14
            if fiber >= 3:
                score += 8
            if sugar <= 10:
                score += 5
            if calories > 450:
                score -= 20
        elif goal == "prise_masse":
            if protein >= 18:
                score += 20
            if 180 <= calories <= 520:
                score += 10
            if carbs >= 20:
                score += 5
        elif goal == "performance":
            if carbs >= 18:
                score += 9
            if protein >= 10:
                score += 9
            if 120 <= calories <= 480:
                score += 8
        else:
            if fiber >= 3:
                score += 10
            if protein >= 8:
                score += 8
            if sugar <= 12:
                score += 6
            if sodium and sodium < 600:
                score += 4
            if fat and fat > 30:
                score -= 8
        return self._clamp(score)

    def _nutrition_safety_score(self, aliment: Aliment, request: RecommendationRequest) -> int:
        score = 100
        constraints = self._normalize(" ".join(request.contraintes_sante))
        sodium = self._safe_float(aliment.sodium_mg)
        sugar = self._safe_float(aliment.sucres_g)
        cholesterol = self._safe_float(aliment.cholesterol_mg)
        if any(term in constraints for term in ("hypertension", "tension", "cardiaque")) and sodium > 700:
            score -= 22
        if any(term in constraints for term in ("diabete", "glycemie")) and sugar > 18:
            score -= 22
        if "cholesterol" in constraints and cholesterol > 120:
            score -= 18
        return self._clamp(score)

    def _nutrition_justification(self, aliment: Aliment, goal: str, request: RecommendationRequest) -> str:
        parts = [f"Selectionne depuis le catalogue aliments pour l'objectif {goal.replace('_', ' ')}."]
        protein = self._safe_float(aliment.proteines_g)
        calories = self._safe_float(aliment.calories_kcal)
        if protein >= 12:
            parts.append("Bon apport proteique pour soutenir la satiete ou la recuperation.")
        if goal == "perte_poids" and calories <= 260:
            parts.append("Densite calorique compatible avec une perte de poids progressive.")
        if request.budget:
            parts.append(f"Budget estime compatible: {self._food_budget_level(aliment)}.")
        if request.preferences_alimentaires and self._preference_bonus(aliment.nom, aliment.categorie, request.preferences_alimentaires):
            parts.append("Correspond a une preference alimentaire declaree.")
        if request.culture_alimentaire:
            parts.append(f"Culture alimentaire demandee: {request.culture_alimentaire}.")
        if request.temps_preparation:
            parts.append(f"Temps de preparation demande: {request.temps_preparation.replace('_', ' ')}.")
        return " ".join(parts)

    def _recipe_hint(self, aliment: Aliment, goal: str) -> str:
        if goal == "perte_poids":
            return f"Portion controlee autour de {aliment.nom}, avec legumes ou crudites si disponibles."
        if goal == "prise_masse":
            return f"Base recette autour de {aliment.nom}, a completer par une source de glucides ou proteines selon le repas."
        if goal == "performance":
            return f"Base energetique autour de {aliment.nom}, utile proche d'une seance selon tolerance digestive."
        return f"Portion simple autour de {aliment.nom}, a integrer dans une assiette equilibree."

    def _nutrition_ingredients(self, aliment: Aliment) -> list[str]:
        ingredients = [aliment.nom]
        if aliment.categorie:
            ingredients.append(aliment.categorie)
        return self._unique_strings(ingredients)

    def _food_budget_level(self, aliment: Aliment) -> str:
        text = self._normalize(f"{aliment.nom} {aliment.categorie or ''}")
        if any(term in text for term in EXPENSIVE_FOOD_TERMS):
            return "eleve"
        if any(term in text for term in ("riz", "pates", "lentille", "haricot", "oeuf", "pomme", "banane", "carotte")):
            return "faible"
        return "moyen"

    def _exercise_equipment(self, exercice: Exercice) -> list[str]:
        items = [exercice.equipement_principal]
        items.extend(self._json_list(exercice.equipments_json))
        seen: set[str] = set()
        cleaned: list[str] = []
        for item in items:
            value = str(item or "").strip()
            key = self._normalize(value)
            if not value or key in seen:
                continue
            seen.add(key)
            cleaned.append(value)
        return cleaned

    def _exercise_muscles(self, exercice: Exercice) -> list[str]:
        items = [
            exercice.body_part_principale,
            exercice.muscle_cible_principal,
            *self._json_list(exercice.body_parts_json),
            *self._json_list(exercice.target_muscles_json),
            *self._json_list(exercice.secondary_muscles_json),
        ]
        seen: set[str] = set()
        muscles: list[str] = []
        for item in items:
            value = str(item or "").strip()
            key = self._normalize(value)
            if value and key not in seen:
                seen.add(key)
                muscles.append(value)
        return muscles

    def _exercise_contraindications(self, exercice: Exercice, constraints: list[str]) -> list[str]:
        if not constraints:
            return []
        text = self._normalize(
            " ".join([
                exercice.nom,
                exercice.body_part_principale or "",
                exercice.muscle_cible_principal or "",
                " ".join(self._exercise_muscles(exercice)),
            ])
        )
        constraint_text = self._normalize(" ".join(constraints))
        contraindications: list[str] = []
        if any(term in constraint_text for term in ("genou", "knee")) and any(term in text for term in ("leg", "upper legs", "quads", "glutes", "calves", "jambe", "squat", "lunge")):
            contraindications.append("contrainte genou: exercice bas du corps evite")
        if any(term in constraint_text for term in ("dos", "lombaire", "back")) and any(term in text for term in ("back", "waist", "spine", "deadlift", "row", "dos")):
            contraindications.append("contrainte dos: charge ou flexion du tronc a eviter")
        if any(term in constraint_text for term in ("epaule", "shoulder")) and any(term in text for term in ("shoulder", "delts", "epaule", "press")):
            contraindications.append("contrainte epaule: amplitude haute a surveiller")
        if any(term in constraint_text for term in ("cardiaque", "coeur", "hypertension", "tension")):
            contraindications.append("contrainte cardio: intensite moderee recommandee")
        return contraindications

    def _has_severe_contraindication(self, contraindications: list[str]) -> bool:
        return any("evite" in item or "a eviter" in item for item in contraindications)

    def _exercise_goal_bonus(self, exercice: Exercice, goal: str) -> int:
        text = self._normalize(f"{exercice.nom} {exercice.body_part_principale or ''} {exercice.muscle_cible_principal or ''}")
        if goal == "prise_masse" and any(term in text for term in ("chest", "back", "legs", "biceps", "triceps", "shoulder", "glutes")):
            return 10
        if goal == "perte_poids" and any(term in text for term in ("cardio", "burpee", "jump", "body weight", "full body")):
            return 8
        if goal == "performance" and any(term in text for term in ("core", "legs", "plyo", "jump", "running")):
            return 8
        if goal == "sante" and any(term in text for term in ("stretch", "mobility", "core", "body weight")):
            return 7
        return 3

    def _requested_muscle_bonus(self, exercice: Exercice, muscles: list[str]) -> int:
        if not muscles:
            return 0
        text = self._normalize(" ".join([exercice.nom, *self._exercise_muscles(exercice)]))
        aliases = {
            "jambes": ("leg", "upper legs", "quads", "hamstrings", "calves", "jambe"),
            "dos": ("back", "lats", "spine", "dos"),
            "poitrine": ("chest", "pectorals", "poitrine"),
            "epaules": ("shoulder", "delts", "epaule"),
            "bras": ("biceps", "triceps", "forearms", "upper arms", "bras"),
            "abdominaux": ("abs", "waist", "core", "abdominaux"),
            "fessiers": ("glutes", "hips", "fessiers"),
        }
        for muscle in muscles:
            key = self._normalize(muscle)
            terms = aliases.get(key, (key,))
            if any(term in text for term in terms):
                return 12
        return 0

    def _session_type_bonus(self, exercice: Exercice, session_type: str | None) -> int:
        if not session_type:
            return 0
        text = self._normalize(f"{exercice.nom} {exercice.body_part_principale or ''} {exercice.instructions_json or ''}")
        session = self._normalize(session_type)
        if session in {"force", "musculation"} and any(term in text for term in ("barbell", "dumbbell", "weighted", "press", "curl", "extension")):
            return 8
        if session == "cardio" and any(term in text for term in ("cardio", "jump", "burpee", "running", "step")):
            return 8
        if session == "mobilite" and any(term in text for term in ("stretch", "mobility", "rotation")):
            return 8
        if session == "recuperation" and any(term in text for term in ("stretch", "breathing", "mobility", "body weight")):
            return 7
        if session == "corps complet" and any(term in text for term in ("full body", "body weight", "core")):
            return 7
        return 0

    def _exercise_level_bonus(self, exercice: Exercice, sport_level: str) -> int:
        text = self._normalize(f"{exercice.nom} {exercice.instructions_json or ''}")
        if sport_level == "debutant" and any(term in text for term in ("assisted", "wall", "body weight", "stretch")):
            return 8
        if sport_level == "avance" and any(term in text for term in ("barbell", "weighted", "advanced")):
            return 8
        return 4 if sport_level == "intermediaire" else 0

    def _exercise_justification(self, exercice: Exercice, goal: str, sport_level: str) -> str:
        muscles = ", ".join(self._exercise_muscles(exercice)[:3]) or "groupes musculaires principaux"
        return (
            f"Exercice compatible avec l'objectif {goal.replace('_', ' ')} et un niveau {sport_level}. "
            f"Muscles cibles: {muscles}."
        )

    def _exercise_duration(self, sport_level: str, preferred_duration: int | None = None) -> int:
        if preferred_duration:
            return max(5, min(45, round(preferred_duration / 4)))
        if sport_level == "avance":
            return 14
        if sport_level == "intermediaire":
            return 11
        return 8

    def _exercise_sets(self, sport_level: str) -> int:
        if sport_level == "avance":
            return 4
        if sport_level == "intermediaire":
            return 3
        return 2

    def _exercise_repetitions(self, sport_level: str, intensity: str) -> str:
        if intensity == "douce":
            return "8 a 10 repetitions controlees"
        if sport_level == "avance":
            return "10 a 15 repetitions"
        return "8 a 12 repetitions"

    def _exercise_rest(self, intensity: str) -> str:
        if intensity == "elevee":
            return "90 s"
        if intensity == "moderee":
            return "60 a 75 s"
        return "45 a 60 s"

    def _exercise_adaptations(self, sport_level: str, health_constraints: list[str]) -> list[str]:
        adaptations: list[str] = []
        if sport_level == "debutant":
            adaptations.append("Amplitude controlee et vitesse lente.")
        normalized_constraints = self._normalize(" ".join(health_constraints))
        if any(term in normalized_constraints for term in ("cardiaque", "coeur", "hypertension", "tension")):
            adaptations.append("Intensite moderee et pauses longues recommandees.")
        return adaptations

    def _sport_intensity(self, sport_level: str, health_constraints: list[str]) -> str:
        health = self._normalize(" ".join(health_constraints))
        if any(term in health for term in ("cardiaque", "coeur", "hypertension", "tension")):
            return "moderee"
        if sport_level == "avance":
            return "elevee"
        if sport_level == "intermediaire":
            return "moderee"
        return "douce"

    def _sport_frequency(self, sport_level: str, goal: str, preferred_frequency: int | None = None) -> str:
        if preferred_frequency is not None:
            return f"{preferred_frequency} fois/semaine"
        if goal == "prise_masse":
            return "3 a 4 fois/semaine" if sport_level != "debutant" else "2 a 3 fois/semaine"
        if goal == "perte_poids":
            return "3 fois/semaine"
        if goal == "performance":
            return "3 a 5 fois/semaine"
        return "2 a 3 fois/semaine"

    def _preference_bonus(self, name: str, category: str | None, preferences: list[str]) -> int:
        if not preferences:
            return 0
        text = self._normalize(f"{name} {category or ''}")
        return 10 if any(self._normalize(pref) in text for pref in preferences if pref) else 0

    def _goal_key(self, value: str | None) -> str:
        text = self._normalize(value or "")
        if any(term in text for term in ("perte", "poids", "minceur", "fat loss")):
            return "perte_poids"
        if any(term in text for term in ("prise", "masse", "muscle", "gain")):
            return "prise_masse"
        if any(term in text for term in ("performance", "sport", "endurance")):
            return "performance"
        if any(term in text for term in ("maintien", "forme", "equilibre")):
            return "maintien"
        return "sante"

    def _sport_level(self, value: str | None) -> str:
        text = self._normalize(value or "")
        if any(term in text for term in ("avance", "expert", "confirme")):
            return "avance"
        if any(term in text for term in ("intermediaire", "moyen")):
            return "intermediaire"
        return "debutant"

    def _canonical_equipment(self, values: list[str]) -> set[str]:
        keys: set[str] = set()
        for raw in values:
            text = self._normalize(str(raw or ""))
            if not text:
                continue
            matched = False
            for key, aliases in EQUIPMENT_ALIASES.items():
                if any(alias and self._normalize(alias) in text for alias in aliases):
                    keys.add(key)
                    matched = True
            if not matched:
                keys.add(text)
        return keys

    def _json_list(self, value: str | None) -> list[str]:
        if not value:
            return []
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError, json.JSONDecodeError):
            return [part.strip() for part in re.split(r"[,;]", str(value)) if part.strip()]
        if isinstance(parsed, list):
            return [str(item) for item in parsed if item]
        return []

    def _unique_strings(self, values) -> list[str]:
        seen: set[str] = set()
        unique: list[str] = []
        for raw in values:
            value = str(raw or "").strip()
            key = self._normalize(value)
            if value and key not in seen:
                seen.add(key)
                unique.append(value)
        return unique

    def _age_from_birthdate(self, birthdate: date | None) -> int | None:
        if birthdate is None:
            return None
        today = date.today()
        return today.year - birthdate.year - ((today.month, today.day) < (birthdate.month, birthdate.day))

    def _normalize(self, value: str) -> str:
        normalized = unicodedata.normalize("NFKD", value or "")
        normalized = "".join(char for char in normalized if not unicodedata.combining(char))
        normalized = normalized.lower().replace("_", " ").replace("-", " ")
        return re.sub(r"\s+", " ", normalized).strip()

    def _safe_float(self, value: Any) -> float:
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0.0

    def _rounded(self, value: Any) -> float | None:
        if value in (None, ""):
            return None
        try:
            return round(float(value), 1)
        except (TypeError, ValueError):
            return None

    def _clamp(self, value: float, lower: int = 0, upper: int = 100) -> int:
        return int(max(lower, min(upper, round(value))))
