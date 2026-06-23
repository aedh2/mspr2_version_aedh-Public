"""ETL admin : workflow lots, detail multi-couches, vue avant/apres."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.db.models import (
    ControleQualiteDonnee,
    EnregistrementBrut,
    ExecutionEtl,
    JournalAlimentaire,
    LotDonnees,
    MesureBiometrique,
    MesureSommeilSante,
    Plat,
    RegleQualite,
    SeanceEntrainement,
    SourceDonnees,
    StgImport,
)

_BUSINESS_TABLES_WITH_LOT = [
    ("mesures_biometriques", MesureBiometrique),
    ("mesures_sommeil_sante", MesureSommeilSante),
    ("seances_entrainement", SeanceEntrainement),
    ("plats", Plat),
    ("journal_alimentaire", JournalAlimentaire),
]


def _serialize_execution(e: ExecutionEtl) -> dict[str, Any]:
    return {
        "execution_id": e.execution_id,
        "source_id": e.source_id,
        "statut": e.statut,
        "demarre_le": e.demarre_le,
        "termine_le": e.termine_le,
        "lignes_lues": e.lignes_lues,
        "lignes_valides": e.lignes_valides,
        "lignes_invalides": e.lignes_invalides,
        "nb_doublons_supprimes": e.nb_doublons_supprimes,
        "nb_valeurs_corrigees": e.nb_valeurs_corrigees,
        "nb_rejets": e.nb_rejets,
        "taux_qualite": e.taux_qualite,
        "message": e.message,
    }


def _serialize_lot(lot: LotDonnees) -> dict[str, Any]:
    return {
        "lot_id": lot.lot_id,
        "execution_id": lot.execution_id,
        "source_id": lot.source_id,
        "nom_lot": lot.nom_lot,
        "statut": lot.statut,
        "cree_par_utilisateur_id": lot.cree_par_utilisateur_id,
        "valide_par_utilisateur_id": lot.valide_par_utilisateur_id,
        "valide_le": lot.valide_le,
        "commentaire_validation": lot.commentaire_validation,
        "cree_le": lot.cree_le,
    }


def _serialize_controle(c: ControleQualiteDonnee) -> dict[str, Any]:
    return {
        "controle_id": c.controle_id,
        "execution_id": c.execution_id,
        "lot_id": c.lot_id,
        "regle_id": c.regle_id,
        "entite": c.entite,
        "ref_externe": c.ref_externe,
        "ref_ligne": c.ref_ligne,
        "nom_champ": c.nom_champ,
        "valeur_observee": c.valeur_observee,
        "valeur_corrigee": c.valeur_corrigee,
        "niveau": c.niveau,
        "type_controle": c.type_controle,
        "decision_finale": c.decision_finale,
        "est_bloquant": c.est_bloquant,
        "code_controle": c.code_controle,
        "etape_pipeline": c.etape_pipeline,
        "description": c.description,
        "cree_le": c.cree_le,
    }


def execution_detail(db: Session, execution_id: int) -> dict[str, Any]:
    e = db.get(ExecutionEtl, execution_id)
    if not e:
        raise ApiError(404, "not_found", "Execution introuvable.")
    src = db.get(SourceDonnees, e.source_id)
    lots = db.execute(
        select(LotDonnees)
        .where(LotDonnees.execution_id == execution_id)
        .order_by(LotDonnees.lot_id.desc())
    ).scalars().all()
    return {
        **_serialize_execution(e),
        "source": {"source_id": src.source_id, "nom": src.nom, "type_source": src.type_source} if src else None,
        "lots": [_serialize_lot(l) for l in lots],
    }


def patch_lot_statut(
    db: Session,
    lot_id: int,
    nouveau_statut: str,
    valide_par_id: int | None,
    commentaire: str | None,
) -> dict[str, Any]:
    autorises = {"EN_ATTENTE", "VALIDE", "REJETE", "ARCHIVE"}
    if nouveau_statut not in autorises:
        raise ApiError(422, "validation_error", f"Statut invalide. Autorises: {', '.join(sorted(autorises))}.")
    lot = db.get(LotDonnees, lot_id)
    if not lot:
        raise ApiError(404, "not_found", "Lot introuvable.")
    lot.statut = nouveau_statut
    if nouveau_statut in {"VALIDE", "REJETE"}:
        lot.valide_par_utilisateur_id = valide_par_id
        lot.valide_le = datetime.utcnow()
        if commentaire is not None:
            lot.commentaire_validation = commentaire
    db.commit()
    db.refresh(lot)
    return _serialize_lot(lot)


def lot_resume(db: Session, lot_id: int) -> dict[str, Any]:
    lot = db.get(LotDonnees, lot_id)
    if not lot:
        raise ApiError(404, "not_found", "Lot introuvable.")
    src = db.get(SourceDonnees, lot.source_id)
    exe = db.get(ExecutionEtl, lot.execution_id)

    nb_raw = db.scalar(select(func.count(EnregistrementBrut.enregistrement_id)).where(EnregistrementBrut.lot_id == lot_id)) or 0
    nb_stg = db.scalar(select(func.count(StgImport.stg_id)).where(StgImport.lot_id == lot_id)) or 0
    nb_controles = db.scalar(select(func.count(ControleQualiteDonnee.controle_id)).where(ControleQualiteDonnee.lot_id == lot_id)) or 0
    nb_bloquants = db.scalar(
        select(func.count(ControleQualiteDonnee.controle_id)).where(
            ControleQualiteDonnee.lot_id == lot_id,
            ControleQualiteDonnee.est_bloquant.is_(True),
        )
    ) or 0

    return {
        **_serialize_lot(lot),
        "source": {"source_id": src.source_id, "nom": src.nom, "type_source": src.type_source} if src else None,
        "execution": _serialize_execution(exe) if exe else None,
        "compteurs": {
            "raw": int(nb_raw),
            "staging": int(nb_stg),
            "controles": int(nb_controles),
            "controles_bloquants": int(nb_bloquants),
        },
    }


def list_raw(
    db: Session, lot_id: int, entite: str | None, page: int, page_size: int
) -> tuple[list[dict[str, Any]], int]:
    if not db.get(LotDonnees, lot_id):
        raise ApiError(404, "not_found", "Lot introuvable.")
    stmt = select(EnregistrementBrut).where(EnregistrementBrut.lot_id == lot_id)
    if entite:
        stmt = stmt.where(EnregistrementBrut.entite == entite)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.execute(
        stmt.order_by(EnregistrementBrut.enregistrement_id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).scalars().all()
    return [
        {
            "enregistrement_id": r.enregistrement_id,
            "entite": r.entite,
            "ref_externe": r.ref_externe,
            "payload_json": r.payload_json,
            "cree_le": r.cree_le,
        }
        for r in rows
    ], int(total)


def list_staging(
    db: Session, lot_id: int, entite: str | None, page: int, page_size: int
) -> tuple[list[dict[str, Any]], int]:
    if not db.get(LotDonnees, lot_id):
        raise ApiError(404, "not_found", "Lot introuvable.")
    stmt = select(StgImport).where(StgImport.lot_id == lot_id)
    if entite:
        stmt = stmt.where(StgImport.entite == entite)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.execute(
        stmt.order_by(StgImport.stg_id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).scalars().all()
    return [
        {
            "stg_id": r.stg_id,
            "entite": r.entite,
            "ref_externe": r.ref_externe,
            "source_payload_json": r.source_payload_json,
            "payload_normalise_json": r.payload_normalise_json,
            "est_parseable": r.est_parseable,
            "statut_validation": r.statut_validation,
            "code_rejet_potentiel": r.code_rejet_potentiel,
            "cree_le": r.cree_le,
        }
        for r in rows
    ], int(total)


def list_controles_lot(
    db: Session, lot_id: int, page: int, page_size: int
) -> tuple[list[dict[str, Any]], int]:
    if not db.get(LotDonnees, lot_id):
        raise ApiError(404, "not_found", "Lot introuvable.")
    stmt = select(ControleQualiteDonnee).where(ControleQualiteDonnee.lot_id == lot_id)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.execute(
        stmt.order_by(ControleQualiteDonnee.controle_id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).scalars().all()
    return [_serialize_controle(c) for c in rows], int(total)


def lot_impacts(db: Session, lot_id: int) -> dict[str, Any]:
    if not db.get(LotDonnees, lot_id):
        raise ApiError(404, "not_found", "Lot introuvable.")
    impacts = {}
    for label, model in _BUSINESS_TABLES_WITH_LOT:
        impacts[label] = int(db.scalar(select(func.count()).where(model.lot_id == lot_id)) or 0)
    return impacts


def compare_avant_apres(
    db: Session,
    lot_id: int,
    entite: str,
    ref_externe: str,
) -> dict[str, Any]:
    if not db.get(LotDonnees, lot_id):
        raise ApiError(404, "not_found", "Lot introuvable.")

    raw = db.execute(
        select(EnregistrementBrut).where(
            EnregistrementBrut.lot_id == lot_id,
            EnregistrementBrut.entite == entite,
            EnregistrementBrut.ref_externe == ref_externe,
        )
    ).scalar_one_or_none()
    stg = db.execute(
        select(StgImport).where(
            StgImport.lot_id == lot_id,
            StgImport.entite == entite,
            StgImport.ref_externe == ref_externe,
        )
    ).scalar_one_or_none()
    controles = _quality_controls_for(db, lot_id=lot_id, entite=entite, ref_externe=ref_externe)

    return {
        "lot_id": lot_id,
        "entite": entite,
        "ref_externe": ref_externe,
        "raw": (
            {"enregistrement_id": raw.enregistrement_id, "payload_json": raw.payload_json, "cree_le": raw.cree_le}
            if raw
            else None
        ),
        "staging": (
            {
                "stg_id": stg.stg_id,
                "source_payload_json": stg.source_payload_json,
                "payload_normalise_json": stg.payload_normalise_json,
                "est_parseable": stg.est_parseable,
                "statut_validation": stg.statut_validation,
                "code_rejet_potentiel": stg.code_rejet_potentiel,
            }
            if stg
            else None
        ),
        "controles": controles,
    }


def compare_options(
    db: Session,
    *,
    lot_id: int | None,
    entite: str | None,
    source_id: int | None,
    ref_externe: str | None,
) -> dict[str, Any]:
    lot_stmt = select(LotDonnees)
    if source_id:
        lot_stmt = lot_stmt.where(LotDonnees.source_id == source_id)
    lots = db.execute(lot_stmt.order_by(LotDonnees.lot_id.desc()).limit(100)).scalars().all()

    entite_stmt = select(StgImport.entite)
    if lot_id:
        entite_stmt = entite_stmt.where(StgImport.lot_id == lot_id)
    if source_id:
        entite_stmt = entite_stmt.join(LotDonnees, LotDonnees.lot_id == StgImport.lot_id).where(LotDonnees.source_id == source_id)
    entites = [row[0] for row in db.execute(entite_stmt.distinct().order_by(StgImport.entite)).all() if row[0]]

    ref_stmt = select(StgImport.ref_externe)
    if lot_id:
        ref_stmt = ref_stmt.where(StgImport.lot_id == lot_id)
    if entite:
        ref_stmt = ref_stmt.where(StgImport.entite == entite)
    if source_id:
        ref_stmt = ref_stmt.join(LotDonnees, LotDonnees.lot_id == StgImport.lot_id).where(LotDonnees.source_id == source_id)
    refs = [row[0] for row in db.execute(ref_stmt.where(StgImport.ref_externe.is_not(None)).distinct().limit(200)).all() if row[0]]
    if ref_externe and ref_externe not in refs:
        refs.insert(0, ref_externe)

    sources = db.execute(
        select(SourceDonnees.source_id, SourceDonnees.nom)
        .join(LotDonnees, LotDonnees.source_id == SourceDonnees.source_id)
        .join(StgImport, StgImport.lot_id == LotDonnees.lot_id)
        .distinct()
        .order_by(SourceDonnees.nom)
    ).all()

    return {
        "lots": [{"id": l.lot_id, "lot_id": l.lot_id, "nom": l.nom_lot, "statut": l.statut} for l in lots],
        "sources": [{"id": row.source_id, "nom": row.nom} for row in sources],
        "entites": entites,
        "refs": refs,
    }


def compare_changes(
    db: Session,
    *,
    lot_id: int | None,
    entite: str | None,
    source_id: int | None,
    ref_externe: str | None,
    changed_only: bool,
    page: int,
    page_size: int,
) -> tuple[list[dict[str, Any]], int]:
    raw_subquery = (
        select(
            EnregistrementBrut.lot_id.label("lot_id"),
            EnregistrementBrut.entite.label("entite"),
            EnregistrementBrut.ref_externe.label("ref_externe"),
            func.max(EnregistrementBrut.enregistrement_id).label("enregistrement_id"),
        )
        .group_by(EnregistrementBrut.lot_id, EnregistrementBrut.entite, EnregistrementBrut.ref_externe)
        .subquery()
    )
    controls_subquery = (
        select(
            ControleQualiteDonnee.lot_id.label("lot_id"),
            ControleQualiteDonnee.entite.label("entite"),
            ControleQualiteDonnee.ref_externe.label("ref_externe"),
            func.count(ControleQualiteDonnee.controle_id).label("nb_controles"),
            func.max(case((ControleQualiteDonnee.valeur_corrigee.is_not(None), 1), else_=0)).label("has_corrected"),
        )
        .group_by(ControleQualiteDonnee.lot_id, ControleQualiteDonnee.entite, ControleQualiteDonnee.ref_externe)
        .subquery()
    )

    stmt = (
        select(StgImport, LotDonnees, SourceDonnees, EnregistrementBrut, controls_subquery.c.nb_controles, controls_subquery.c.has_corrected)
        .join(LotDonnees, LotDonnees.lot_id == StgImport.lot_id)
        .join(SourceDonnees, SourceDonnees.source_id == LotDonnees.source_id)
        .outerjoin(
            raw_subquery,
            and_(
                raw_subquery.c.lot_id == StgImport.lot_id,
                raw_subquery.c.entite == StgImport.entite,
                raw_subquery.c.ref_externe == StgImport.ref_externe,
            ),
        )
        .outerjoin(EnregistrementBrut, EnregistrementBrut.enregistrement_id == raw_subquery.c.enregistrement_id)
        .outerjoin(
            controls_subquery,
            and_(
                controls_subquery.c.lot_id == StgImport.lot_id,
                controls_subquery.c.entite == StgImport.entite,
                controls_subquery.c.ref_externe == StgImport.ref_externe,
            ),
        )
        .where(StgImport.payload_normalise_json.is_not(None))
    )
    if lot_id:
        stmt = stmt.where(StgImport.lot_id == lot_id)
    if entite:
        stmt = stmt.where(func.lower(StgImport.entite) == entite.lower())
    if source_id:
        stmt = stmt.where(LotDonnees.source_id == source_id)
    if ref_externe:
        stmt = stmt.where(StgImport.ref_externe == ref_externe)

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.execute(
        stmt.order_by(
            func.coalesce(controls_subquery.c.nb_controles, 0).desc(),
            func.coalesce(controls_subquery.c.has_corrected, 0).desc(),
            func.coalesce(StgImport.statut_validation, "").asc(),
            StgImport.stg_id.desc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    data: list[dict[str, Any]] = []
    for stg, lot, source, raw, nb_controles, has_corrected in rows:
        if raw is None:
            raw = _fallback_raw_for_staging(db, stg)
        raw_payload = raw.payload_json if raw else None
        normalized_payload = stg.payload_normalise_json
        has_changes = _has_payload_changes(raw_payload, normalized_payload) or bool(nb_controles) or bool(has_corrected)
        if changed_only and not has_changes:
            continue
        quality_controls = _quality_controls_for(db, lot_id=stg.lot_id, entite=stg.entite, ref_externe=stg.ref_externe)
        data.append(
            {
                "lot": {"id": lot.lot_id, "nom": lot.nom_lot},
                "source": {"id": source.source_id, "nom": source.nom},
                "entite": stg.entite,
                "ref_externe": stg.ref_externe,
                "raw": (
                    {
                        "id": raw.enregistrement_id,
                        "payload_json": _jsonish(raw_payload),
                    }
                    if raw
                    else None
                ),
                "staging": {
                    "id": stg.stg_id,
                    "payload_normalise_json": _jsonish(normalized_payload),
                    "source_payload_json": _jsonish(stg.source_payload_json),
                    "statut_validation": stg.statut_validation,
                    "code_rejet_potentiel": stg.code_rejet_potentiel,
                    "est_parseable": stg.est_parseable,
                },
                "quality_controls": quality_controls,
                "has_changes": has_changes,
            }
        )
    return data, int(total)


def _quality_controls_for(db: Session, *, lot_id: int, entite: str, ref_externe: str | None) -> list[dict[str, Any]]:
    controles_rows = db.execute(
        select(ControleQualiteDonnee, RegleQualite)
        .join(RegleQualite, RegleQualite.regle_id == ControleQualiteDonnee.regle_id, isouter=True)
        .where(
            ControleQualiteDonnee.lot_id == lot_id,
            ControleQualiteDonnee.entite == entite,
            ControleQualiteDonnee.ref_externe == ref_externe,
        )
        .order_by(ControleQualiteDonnee.controle_id.asc())
    ).all()
    return [
        {
            **_serialize_controle(c),
            "regle": (
                {
                    "regle_id": r.regle_id,
                    "code_regle": r.code_regle,
                    "type_regle": r.type_regle,
                    "severite": r.severite,
                    "description": r.description,
                }
                if r is not None
                else None
            ),
        }
        for c, r in controles_rows
    ]


def _jsonish(payload: str | None) -> Any:
    if payload in (None, ""):
        return None
    try:
        return json.loads(payload)
    except Exception:
        return payload


def _has_payload_changes(raw_payload: str | None, normalized_payload: str | None) -> bool:
    return _jsonish(raw_payload) != _jsonish(normalized_payload)


def _fallback_raw_for_staging(db: Session, stg: StgImport) -> EnregistrementBrut | None:
    stmt = select(EnregistrementBrut).where(EnregistrementBrut.lot_id == stg.lot_id)
    if stg.entite:
        stmt = stmt.where(EnregistrementBrut.entite == stg.entite)
    if stg.ref_externe:
        candidate = db.execute(
            stmt.where(EnregistrementBrut.ref_externe == stg.ref_externe).order_by(EnregistrementBrut.enregistrement_id.desc()).limit(1)
        ).scalar_one_or_none()
        if candidate is not None:
            return candidate
    return db.execute(stmt.order_by(EnregistrementBrut.enregistrement_id.desc()).limit(1)).scalar_one_or_none()
