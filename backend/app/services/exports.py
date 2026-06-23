"""Exports CSV en streaming.

Implémentation minimale stdlib (pas de pandas/openpyxl). Stream ligne par ligne
pour ne pas charger l'intégralité en mémoire sur de gros volumes.
"""
from __future__ import annotations

import csv
import io
from typing import Any, Iterable, Iterator

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    ControleQualiteDonnee,
    ExecutionEtl,
    JournalAlimentaire,
    LotDonnees,
    MesureBiometrique,
    MesureSommeilSante,
    Plat,
    SeanceEntrainement,
    Utilisateur,
)


def _csv_iter(headers: list[str], rows: Iterable[Iterable[Any]]) -> Iterator[str]:
    buffer = io.StringIO()
    writer = csv.writer(buffer, quoting=csv.QUOTE_MINIMAL)

    writer.writerow(headers)
    yield buffer.getvalue()
    buffer.seek(0)
    buffer.truncate(0)

    for row in rows:
        writer.writerow(["" if v is None else v for v in row])
        yield buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)


def export_utilisateurs(db: Session) -> Iterator[str]:
    headers = [
        "utilisateur_id", "organisation_id", "nom_utilisateur", "prenom", "nom",
        "email", "role", "statut", "date_naissance", "genre", "taille_cm", "cree_le",
    ]

    def rows() -> Iterator[list[Any]]:
        for u in db.execute(select(Utilisateur)).scalars():
            yield [
                u.utilisateur_id, u.organisation_id, u.nom_utilisateur, u.prenom, u.nom,
                u.email, u.role, u.statut, u.date_naissance, u.genre, u.taille_cm, u.cree_le,
            ]

    return _csv_iter(headers, rows())


def export_biometrie(db: Session) -> Iterator[str]:
    headers = [
        "mesure_id", "utilisateur_id", "mesure_le", "poids_kg", "taille_cm", "imc",
        "taux_masse_grasse", "bpm_repos", "bpm_moyen", "bpm_max", "eau_l",
    ]

    def rows() -> Iterator[list[Any]]:
        for m in db.execute(select(MesureBiometrique)).scalars():
            yield [
                m.mesure_id, m.utilisateur_id, m.mesure_le, m.poids_kg, m.taille_cm, m.imc,
                m.taux_masse_grasse, m.bpm_repos, m.bpm_moyen, m.bpm_max, m.eau_l,
            ]

    return _csv_iter(headers, rows())


def export_sommeil(db: Session) -> Iterator[str]:
    headers = [
        "mesure_sommeil_id", "utilisateur_id", "mesure_le", "duree_sommeil_h",
        "qualite_sommeil_score", "stress_score", "pas_jour", "frequence_cardiaque_bpm",
        "tension_systolique", "tension_diastolique", "trouble_sommeil_normalise",
    ]

    def rows() -> Iterator[list[Any]]:
        for m in db.execute(select(MesureSommeilSante)).scalars():
            yield [
                m.mesure_sommeil_id, m.utilisateur_id, m.mesure_le, m.duree_sommeil_h,
                m.qualite_sommeil_score, m.stress_score, m.pas_jour, m.frequence_cardiaque_bpm,
                m.tension_systolique, m.tension_diastolique, m.trouble_sommeil_normalise,
            ]

    return _csv_iter(headers, rows())


def export_sport(db: Session) -> Iterator[str]:
    headers = [
        "seance_id", "utilisateur_id", "date_seance", "type_entrainement",
        "duree_seance_min", "calories_brulees_total", "frequence_entrainement_j_sem",
        "niveau_experience", "eau_l",
    ]

    def rows() -> Iterator[list[Any]]:
        for s in db.execute(select(SeanceEntrainement)).scalars():
            yield [
                s.seance_id, s.utilisateur_id, s.date_seance, s.type_entrainement,
                s.duree_seance_min, s.calories_brulees_total, s.frequence_entrainement_j_sem,
                s.niveau_experience, s.eau_l,
            ]

    return _csv_iter(headers, rows())


def export_nutrition(db: Session) -> Iterator[str]:
    headers = [
        "journal_id", "utilisateur_id", "plat_id", "aliment_id", "consomme_le",
        "type_repas", "aliment_nom_libre", "quantite", "unite_quantite",
        "calories_kcal", "eau_ml",
    ]

    def rows() -> Iterator[list[Any]]:
        for j in db.execute(select(JournalAlimentaire)).scalars():
            yield [
                j.journal_id, j.utilisateur_id, j.plat_id, j.aliment_id, j.consomme_le,
                j.type_repas, j.aliment_nom_libre, j.quantite, j.unite_quantite,
                j.calories_kcal, j.eau_ml,
            ]

    return _csv_iter(headers, rows())


def export_qualite(db: Session) -> Iterator[str]:
    headers = [
        "controle_id", "execution_id", "lot_id", "regle_id", "entite", "ref_externe",
        "nom_champ", "niveau", "type_controle", "decision_finale", "est_bloquant",
        "code_controle", "etape_pipeline", "cree_le",
    ]

    def rows() -> Iterator[list[Any]]:
        for c in db.execute(select(ControleQualiteDonnee)).scalars():
            yield [
                c.controle_id, c.execution_id, c.lot_id, c.regle_id, c.entite, c.ref_externe,
                c.nom_champ, c.niveau, c.type_controle, c.decision_finale, c.est_bloquant,
                c.code_controle, c.etape_pipeline, c.cree_le,
            ]

    return _csv_iter(headers, rows())


def export_executions(db: Session) -> Iterator[str]:
    headers = [
        "execution_id", "source_id", "statut", "demarre_le", "termine_le",
        "lignes_lues", "lignes_valides", "lignes_invalides", "nb_doublons_supprimes",
        "nb_valeurs_corrigees", "nb_rejets", "taux_qualite",
    ]

    def rows() -> Iterator[list[Any]]:
        for e in db.execute(select(ExecutionEtl)).scalars():
            yield [
                e.execution_id, e.source_id, e.statut, e.demarre_le, e.termine_le,
                e.lignes_lues, e.lignes_valides, e.lignes_invalides, e.nb_doublons_supprimes,
                e.nb_valeurs_corrigees, e.nb_rejets, e.taux_qualite,
            ]

    return _csv_iter(headers, rows())


def export_lots(db: Session) -> Iterator[str]:
    headers = [
        "lot_id", "execution_id", "source_id", "nom_lot", "statut",
        "cree_par_utilisateur_id", "valide_par_utilisateur_id", "valide_le",
        "commentaire_validation", "cree_le",
    ]

    def rows() -> Iterator[list[Any]]:
        for l in db.execute(select(LotDonnees)).scalars():
            yield [
                l.lot_id, l.execution_id, l.source_id, l.nom_lot, l.statut,
                l.cree_par_utilisateur_id, l.valide_par_utilisateur_id, l.valide_le,
                l.commentaire_validation, l.cree_le,
            ]

    return _csv_iter(headers, rows())


def export_plats(db: Session) -> Iterator[str]:
    headers = [
        "plat_id", "utilisateur_id", "consomme_le", "type_repas",
        "nom_plat", "calories_totales_kcal",
    ]

    def rows() -> Iterator[list[Any]]:
        for p in db.execute(select(Plat)).scalars():
            yield [
                p.plat_id, p.utilisateur_id, p.consomme_le, p.type_repas,
                p.nom_plat, p.calories_totales_kcal,
            ]

    return _csv_iter(headers, rows())


EXPORTERS = {
    "utilisateurs": export_utilisateurs,
    "biometrie": export_biometrie,
    "sommeil": export_sommeil,
    "sport": export_sport,
    "nutrition": export_nutrition,
    "qualite": export_qualite,
    "executions": export_executions,
    "lots": export_lots,
    "plats": export_plats,
}
