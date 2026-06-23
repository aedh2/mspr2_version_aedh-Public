"""Endpoints additionnels du catalogue exercices.

Doit être inclus AVANT le CRUD générique `/exercices/{item_id}` dans api.py,
sinon `/exercices/filters` est intercepté par le path paramétrique et renvoie 422.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import distinct, select
from sqlalchemy.orm import Session

from app.core.security import current_user
from app.db.models import Exercice, Utilisateur
from app.db.session import get_db

router = APIRouter(prefix="/exercices", tags=["exercices"])


@router.get("/filters")
def filters(
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(current_user),
) -> dict[str, Any]:
    """Renvoie les valeurs distinctes utilisables comme filtres côté front."""
    body_parts = sorted(
        v[0]
        for v in db.execute(
            select(distinct(Exercice.body_part_principale)).where(
                Exercice.body_part_principale.is_not(None)
            )
        ).all()
        if v[0]
    )
    target_muscles = sorted(
        v[0]
        for v in db.execute(
            select(distinct(Exercice.muscle_cible_principal)).where(
                Exercice.muscle_cible_principal.is_not(None)
            )
        ).all()
        if v[0]
    )
    equipements = sorted(
        v[0]
        for v in db.execute(
            select(distinct(Exercice.equipement_principal)).where(
                Exercice.equipement_principal.is_not(None)
            )
        ).all()
        if v[0]
    )
    return {
        "data": {
            "body_parts": body_parts,
            "target_muscles": target_muscles,
            "equipements": equipements,
        }
    }
