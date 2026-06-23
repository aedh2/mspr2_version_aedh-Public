from __future__ import annotations

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import current_user, require_roles
from app.db.models import (
    Aliment,
    ControleQualiteDonnee,
    ExecutionEtl,
    JournalAlimentaire,
    MesureBiometrique,
    MesureSommeilSante,
    Plat,
    SeanceEntrainement,
    Utilisateur,
    ProgressionPhoto,
)
from app.db.session import get_db
from app.modules.resources import serialize_model
from app.services import me_metrics, me_nutrition, me_sport

router = APIRouter(tags=["dashboards"])


@router.get("/me/dashboard")
def me_dashboard(db: Session = Depends(get_db), user: Utilisateur = Depends(current_user)) -> dict:
    uid = user.utilisateur_id
    today = date.today()
    start_of_day = datetime.combine(today, datetime.min.time())
    end_of_day = start_of_day + timedelta(days=1)
    latest_bio = db.execute(
        select(MesureBiometrique).where(MesureBiometrique.utilisateur_id == uid).order_by(MesureBiometrique.mesure_le.desc())
    ).scalars().first()
    latest_sleep = db.execute(
        select(MesureSommeilSante)
        .where(MesureSommeilSante.utilisateur_id == uid)
        .order_by(MesureSommeilSante.mesure_le.desc())
    ).scalars().first()
    active_objectif = me_metrics.objectif_actif(db, uid)
    latest_photo = me_metrics.latest_progress_photo(db, uid, preferred_type="AFTER")
    recent_seances = db.execute(
        select(SeanceEntrainement).where(SeanceEntrainement.utilisateur_id == uid).order_by(SeanceEntrainement.date_seance.desc()).limit(5)
    ).scalars().all()
    recent_meals = db.execute(
        select(Plat).where(Plat.utilisateur_id == uid).order_by(Plat.consomme_le.desc()).limit(5)
    ).scalars().all()
    bio_rows = db.execute(
        select(MesureBiometrique).where(MesureBiometrique.utilisateur_id == uid).order_by(MesureBiometrique.mesure_le.asc())
    ).scalars().all()
    sleep_rows = db.execute(
        select(MesureSommeilSante).where(MesureSommeilSante.utilisateur_id == uid).order_by(MesureSommeilSante.mesure_le.asc())
    ).scalars().all()
    payload = {
            "utilisateur_id": uid,
            "dernier_poids_kg": None if not latest_bio else latest_bio.poids_kg,
            "dernier_imc": None if not latest_bio else latest_bio.imc,
            "derniere_duree_sommeil_h": None if not latest_sleep else latest_sleep.duree_sommeil_h,
            "nb_seances": db.scalar(select(func.count()).where(SeanceEntrainement.utilisateur_id == uid)) or 0,
            "nb_plats": db.scalar(select(func.count()).where(Plat.utilisateur_id == uid)) or 0,
            "calories_journal": db.scalar(
                select(func.coalesce(func.sum(JournalAlimentaire.calories_kcal), 0)).where(
                    JournalAlimentaire.utilisateur_id == uid,
                    JournalAlimentaire.consomme_le >= start_of_day,
                    JournalAlimentaire.consomme_le < end_of_day,
                )
            )
            or 0,
            "calories_brulees": db.scalar(
                select(func.coalesce(func.sum(SeanceEntrainement.calories_brulees_total), 0)).where(SeanceEntrainement.utilisateur_id == uid)
            ) or 0,
            "objectif_actif": active_objectif,
            "derniere_photo": latest_photo,
            "dernieres_seances": [serialize_model(row) for row in recent_seances],
            "derniers_repas": [serialize_model(row) for row in recent_meals],
            "biometrie": {
                "poids": [{"bucket": r.mesure_le.date().isoformat(), "value": r.poids_kg} for r in bio_rows],
                "imc": [{"bucket": r.mesure_le.date().isoformat(), "value": r.imc} for r in bio_rows],
            },
            "sommeil": [{"bucket": r.mesure_le.date().isoformat(), "value": r.duree_sommeil_h} for r in sleep_rows],
            "entrainements_par_type": me_sport.seances_kpis(db, uid)["top_types_30j"],
            "nutrition": {"calories_par_bucket": []},
    }
    return {"data": payload}


@router.get("/admin/dashboard")
def admin_dashboard(
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(require_roles("ADMIN", "SUPER_ADMIN")),
) -> dict:
    return {
        "data": {
            "nb_utilisateurs": db.scalar(select(func.count()).select_from(Utilisateur)) or 0,
            "nb_aliments": db.scalar(select(func.count()).select_from(Aliment)) or 0,
            "nb_executions_etl": db.scalar(select(func.count()).select_from(ExecutionEtl)) or 0,
            "taux_qualite_moyen": db.scalar(select(func.avg(ExecutionEtl.taux_qualite))) or 0,
            "controles_bloquants": db.scalar(
                select(func.count()).where(ControleQualiteDonnee.est_bloquant.is_(True))
            )
            or 0,
        }
    }


@router.get("/admin/dashboard/kpis")
def admin_dashboard_kpis(
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(require_roles("ADMIN", "SUPER_ADMIN")),
) -> dict:
    return admin_dashboard(db, _)


@router.get("/super-admin/dashboard")
def super_admin_dashboard(
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(require_roles("SUPER_ADMIN")),
) -> dict:
    return {
        "data": {
            "nb_utilisateurs": db.scalar(select(func.count()).select_from(Utilisateur)) or 0,
            "nb_admins": db.scalar(select(func.count()).where(Utilisateur.role.in_(["ADMIN", "SUPER_ADMIN"]))) or 0,
            "nb_executions_etl": db.scalar(select(func.count()).select_from(ExecutionEtl)) or 0,
            "qualite_min": db.scalar(select(func.min(ExecutionEtl.taux_qualite))) or 0,
            "qualite_max": db.scalar(select(func.max(ExecutionEtl.taux_qualite))) or 0,
        }
    }
