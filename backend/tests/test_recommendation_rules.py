from __future__ import annotations

from app.db.models import Exercice
from app.services.recommendations import RecommendationEngine


def test_food_allergy_alias_blocks_incompatible_food():
    engine = RecommendationEngine()

    reasons = engine.food_block_reasons("Beurre de cacahuete", "Tartinable", ["arachide"], None)

    assert reasons
    assert "allergie" in reasons[0]


def test_equipment_rule_rejects_missing_material_and_allows_bodyweight():
    engine = RecommendationEngine()

    assert engine.equipment_is_allowed(["body weight"], []) is True
    assert engine.equipment_is_allowed(["dumbbell"], ["tapis"]) is False
    assert engine.equipment_is_allowed(["dumbbell"], ["halteres"]) is True


def test_health_constraint_marks_knee_sensitive_exercise_as_severe():
    engine = RecommendationEngine()
    exercice = Exercice(
        exercice_id=1,
        nom="Squat",
        body_part_principale="upper legs",
        muscle_cible_principal="quads",
    )

    contraindications = engine._exercise_contraindications(exercice, ["douleur genou"])

    assert contraindications
    assert engine._has_severe_contraindication(contraindications) is True
