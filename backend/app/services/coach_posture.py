from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.exc import DataError, IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import ApiError
from app.db.models import CoachPostureSession, Utilisateur
from app.schemas.coach_posture import (
    CoachPostureFeedbackRequest,
    CoachPostureFeedbackResponse,
    CoachPostureHistoryItem,
    CoachPostureValidationItem,
    CoachPostureValidationRequest,
    CoachPostureValidationResponse,
    CoachPostureValidationSummary,
)
from app.services.coach_posture_logic import PostureStatus

logger = logging.getLogger(__name__)


class CoachPostureService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def feedback(self, payload: CoachPostureFeedbackRequest) -> CoachPostureFeedbackResponse:
        local_response = self._local_feedback(payload)
        if not self.settings.ai_enable_external_calls or not self.settings.deepseek_api_key:
            return local_response

        external_response = self._try_deepseek_feedback(payload, local_response)
        return external_response or local_response

    def validate_exercise(
        self,
        db: Session,
        user: Utilisateur,
        payload: CoachPostureValidationRequest,
    ) -> CoachPostureValidationResponse:
        validated_at = payload.validated_at or datetime.utcnow()
        try:
            self._ensure_history_table(db)
            row = CoachPostureSession(
                utilisateur_id=user.utilisateur_id,
                exercice_code=payload.exercise[:80],
                exercice_nom=payload.exercise_label[:120],
                type_exercice=payload.type,
                statut_posture=payload.status,
                score_alignement=payload.score_alignement,
                reps=payload.reps,
                reps_in_current_set=payload.reps_in_current_set,
                sets_count=payload.sets,
                hold_seconds=payload.hold_seconds,
                best_hold_seconds=payload.best_hold_seconds,
                validated_holds=self._validated_holds_count(payload.validated_holds),
                detected_errors_json=json.dumps(payload.detected_errors, ensure_ascii=True),
                feedback_json=json.dumps(payload.feedback, ensure_ascii=True) if payload.feedback else None,
                snapshot_path=None,
                source_page="coach_posture",
                valide_le=validated_at.replace(tzinfo=None),
                cree_le=datetime.utcnow(),
            )
            db.add(row)
            db.commit()
            db.refresh(row)
        except (DataError, IntegrityError, SQLAlchemyError) as exc:
            db.rollback()
            logger.warning("Coach posture validation persistence failed: %s", exc)
            raise ApiError(
                409,
                "conflict",
                "Impossible d'enregistrer l'exercice dans l'historique coach posture.",
                str(getattr(exc, "orig", exc)),
            ) from exc

        item = self._history_item_from_row(row, payload.detected_errors)
        return CoachPostureValidationResponse(
            validation_id=str(row.coach_posture_id),
            exercise=payload.exercise,
            saved=True,
            item=item.item,
            summary=CoachPostureValidationSummary(
                exercise=payload.exercise,
                type=payload.type,
                reps=payload.reps,
                reps_in_current_set=payload.reps_in_current_set,
                sets=payload.sets,
                hold_seconds=payload.hold_seconds,
                score_alignement=payload.score_alignement,
            ),
        )

    def recent_history(self, db: Session, user: Utilisateur, limit: int = 20) -> list[CoachPostureHistoryItem]:
        try:
            self._ensure_history_table(db)
            rows = db.execute(
                select(CoachPostureSession)
                .where(CoachPostureSession.utilisateur_id == user.utilisateur_id)
                .order_by(CoachPostureSession.valide_le.desc(), CoachPostureSession.coach_posture_id.desc())
                .limit(max(1, min(limit, 20)))
            ).scalars().all()
        except SQLAlchemyError as exc:
            db.rollback()
            logger.warning("Coach posture history read failed: %s", exc)
            raise ApiError(
                409,
                "conflict",
                "Impossible de lire l'historique coach posture.",
                str(getattr(exc, "orig", exc)),
            ) from exc

        return [self._history_item_from_row(row) for row in rows]

    def _local_feedback(self, payload: CoachPostureFeedbackRequest) -> CoachPostureFeedbackResponse:
        errors = payload.detected_errors[:3] or self._default_errors(payload)
        conseils = self._local_tips(payload.exercise, payload.status, errors)
        encouragement = self._encouragement(payload.status, payload.score_alignement)
        return CoachPostureFeedbackResponse(
            mode="local",
            exercise=payload.exercise,
            statut_posture=payload.status,
            erreurs_principales=errors,
            conseils=conseils,
            encouragement=encouragement,
            repetitions=payload.reps,
            sets=payload.sets,
            chrono=payload.hold_seconds,
            score_alignement=payload.score_alignement,
        )

    def _ensure_history_table(self, db: Session) -> None:
        CoachPostureSession.__table__.create(bind=db.get_bind(), checkfirst=True)

    def _history_item_from_row(
        self,
        row: CoachPostureSession,
        detected_errors: list[str] | None = None,
    ) -> CoachPostureHistoryItem:
        errors = detected_errors if detected_errors is not None else self._json_list(row.detected_errors_json)
        item = CoachPostureValidationItem(
            coach_posture_id=row.coach_posture_id,
            exercise=row.exercice_code,
            exercise_label=row.exercice_nom,
            type="static" if row.type_exercice == "static" else "dynamic",
            status=self._decode_status(row.statut_posture),
            score_alignement=row.score_alignement,
            reps=row.reps,
            reps_in_current_set=row.reps_in_current_set,
            sets=row.sets_count,
            hold_seconds=row.hold_seconds,
            best_hold_seconds=row.best_hold_seconds,
            validated_holds=row.validated_holds,
            snapshot_path=row.snapshot_path,
            validated_at=row.valide_le,
        )
        return CoachPostureHistoryItem(
            validation_id=str(row.coach_posture_id),
            message="Exercice enregistre",
            exercise=row.exercice_code,
            saved=True,
            item=item,
            summary=CoachPostureValidationSummary(
                exercise=row.exercice_code,
                type=item.type,
                reps=row.reps,
                reps_in_current_set=row.reps_in_current_set,
                sets=row.sets_count,
                hold_seconds=row.hold_seconds,
                score_alignement=row.score_alignement,
            ),
            validated_at=row.valide_le,
            exercise_label=row.exercice_nom,
            type=item.type,
            status=item.status,
            detected_errors=errors,
            snapshot_path=row.snapshot_path,
        )

    def _validated_holds_count(self, value: int | list[int]) -> int:
        if isinstance(value, list):
            return len(value)
        return max(0, int(value or 0))

    def _json_list(self, raw: str | None) -> list[str]:
        if not raw:
            return []
        try:
            data = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            return []
        return self._as_string_list(data, [])

    def _decode_status(self, value: Any) -> PostureStatus:
        if value in {"incorrect", "almost", "correct"}:
            return value
        return "incorrect"

    def _try_deepseek_feedback(
        self,
        payload: CoachPostureFeedbackRequest,
        fallback: CoachPostureFeedbackResponse,
    ) -> CoachPostureFeedbackResponse | None:
        url = f"{self.settings.effective_deepseek_base_url.rstrip('/')}/chat/completions"
        prompt = {
            "exercise": payload.exercise,
            "status": payload.status,
            "angles": payload.angles,
            "detected_errors": payload.detected_errors,
            "reps": payload.reps,
            "reps_in_current_set": payload.reps_in_current_set,
            "sets": payload.sets,
            "hold_seconds": payload.hold_seconds,
            "best_hold_seconds": payload.best_hold_seconds,
            "validated_holds": payload.validated_holds,
            "score_alignement": payload.score_alignement,
            "person_detected": payload.person_detected,
        }
        try:
            response = httpx.post(
                url,
                headers={
                    "Authorization": f"Bearer {self.settings.deepseek_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.settings.effective_deepseek_model,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "Tu es un coach sportif prudent. Reponds uniquement en JSON compact avec les cles "
                                "erreurs_principales, conseils, safety_warning, encouragement. "
                                "Ne diagnostique aucune blessure."
                            ),
                        },
                        {"role": "user", "content": json.dumps(prompt, ensure_ascii=True)},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 350,
                },
                timeout=8.0,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            data = json.loads(content)
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError):
            logger.warning("DeepSeek posture feedback failed.")
            return None

        return CoachPostureFeedbackResponse(
            mode="external",
            exercise=payload.exercise,
            statut_posture=payload.status,
            erreurs_principales=self._as_string_list(data.get("erreurs_principales"), fallback.erreurs_principales),
            conseils=self._as_string_list(data.get("conseils"), fallback.conseils),
            safety_warning=str(data.get("safety_warning") or fallback.safety_warning),
            encouragement=str(data.get("encouragement") or fallback.encouragement),
            repetitions=payload.reps,
            sets=payload.sets,
            chrono=payload.hold_seconds,
            score_alignement=payload.score_alignement,
        )

    def _default_errors(self, payload: CoachPostureFeedbackRequest) -> list[str]:
        if payload.status == "correct":
            return []
        if payload.exercise == "gainage":
            return ["alignement epaules hanches chevilles a stabiliser"]
        if payload.exercise == "curl_biceps":
            return ["controle du coude a ameliorer"]
        if payload.exercise == "push_up":
            return ["alignement epaules hanches chevilles a stabiliser"]
        if payload.exercise == "wall_sit":
            return ["angle genoux hanches a stabiliser"]
        if payload.exercise == "tree_pose":
            return ["equilibre et alignement a stabiliser"]
        return ["alignement genoux hanches a verifier"]

    def _local_tips(self, exercise: str, status: PostureStatus, errors: list[str]) -> list[str]:
        _ = errors
        if status == "correct":
            if exercise == "wall_sit":
                return ["Position correcte, maintien en cours.", "Respire regulierement."]
            if exercise == "tree_pose":
                return ["Position correcte, maintien en cours.", "Garde le regard stable et respire calmement."]
            return ["Garde ce rythme et conserve une respiration stable."]
        tips_by_exercise = {
            "squat": ["Redresse legerement le buste.", "Garde les genoux alignes avec les pieds."],
            "curl_biceps": ["Garde les coudes proches du buste.", "Controle la descente sans balancer les epaules."],
            "push_up": ["Garde le corps aligne.", "Descends sans casser les hanches puis verrouille la remontee."],
            "gainage": ["Aligne epaules, hanches et chevilles.", "Rentre legerement le bassin et respire calmement."],
            "wall_sit": ["Garde le buste droit.", "Stabilise les genoux autour de 90 degres."],
            "tree_pose": ["Redresse le buste.", "Stabilise la jambe d'appui et garde le pied pose contre la jambe opposee."],
        }
        tips = tips_by_exercise.get(exercise, ["Ralentis le mouvement et cherche un alignement stable."])
        if status == "incorrect":
            return [tips[0], "Reprends une amplitude plus courte avant d'accelerer."]
        return tips

    def _encouragement(self, status: PostureStatus, score: int) -> str:
        if status == "correct":
            return "Tres bon alignement, continue sur cette qualite."
        if status == "almost" or score >= 65:
            return "Bonne progression, il manque seulement quelques ajustements."
        return "Ralentis et reconstruis le mouvement proprement."

    def _as_string_list(self, value: Any, fallback: list[str]) -> list[str]:
        if not isinstance(value, list):
            return fallback
        cleaned = [str(item).strip() for item in value if str(item).strip()]
        return cleaned[:4] or fallback

    def _as_int(self, value: Any, fallback: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return fallback
