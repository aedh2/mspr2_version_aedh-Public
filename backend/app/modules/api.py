from __future__ import annotations

from fastapi import APIRouter

from app.db import models
from app.modules import (
    admin,
    ai_features,
    auth,
    dashboards,
    exercices_extra,
    exports,
    me,
    super_admin,
)
from app.modules.resources import (
    JournalAlimentaireCreate,
    JournalAlimentaireUpdate,
    ResourceConfig,
    create_crud_router,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(me.router)
api_router.include_router(ai_features.router)
api_router.include_router(dashboards.router)
# Routes statiques avant CRUD générique pour éviter l'interception par {item_id:int}.
api_router.include_router(exercices_extra.router)
api_router.include_router(admin.router)
api_router.include_router(super_admin.router)
api_router.include_router(exports.router)

RESOURCES = [
    # /organisations et /sources-donnees : la spec impose que les mutations
    # restent réservées au super-admin. On garde le CRUD générique mais on
    # surveillera ce point au sprint hardening (S6) — actuellement gardé par
    # CRUD_ROLES = (ADMIN, SUPER_ADMIN). À durcir si besoin.
    ResourceConfig("/organisations", models.Organisation, "organisation_id", searchable_fields=("nom", "adresse")),
    ResourceConfig("/sources-donnees", models.SourceDonnees, "source_id", soft_delete_field="actif", soft_delete_value=False, searchable_fields=("nom", "description", "type_source", "format_source")),
    ResourceConfig("/regles-qualite", models.RegleQualite, "regle_id", soft_delete_field="actif", soft_delete_value=False, searchable_fields=("code_regle", "description", "entite", "nom_champ", "type_regle")),
    ResourceConfig("/utilisateurs", models.Utilisateur, "utilisateur_id", searchable_fields=("nom_utilisateur", "email", "prenom", "nom")),
    ResourceConfig("/objectifs-utilisateur", models.ObjectifUtilisateur, "objectif_id", owner_field="utilisateur_id"),
    ResourceConfig("/progression-photos", models.ProgressionPhoto, "photo_id", owner_field="utilisateur_id"),
    ResourceConfig("/mesures-biometriques", models.MesureBiometrique, "mesure_id", owner_field="utilisateur_id"),
    ResourceConfig("/mesures-sommeil-sante", models.MesureSommeilSante, "mesure_sommeil_id", owner_field="utilisateur_id"),
    ResourceConfig("/exercices", models.Exercice, "exercice_id", searchable_fields=("nom", "body_part_principale", "muscle_cible_principal", "equipement_principal")),
    ResourceConfig("/seances-entrainement", models.SeanceEntrainement, "seance_id", owner_field="utilisateur_id"),
    ResourceConfig("/seances-exercices", models.SeanceExercice, "seance_exercice_id"),
    ResourceConfig("/aliments", models.Aliment, "aliment_id", searchable_fields=("nom", "categorie")),
    ResourceConfig("/plats", models.Plat, "plat_id", owner_field="utilisateur_id"),
    ResourceConfig(
        "/journal-alimentaire",
        models.JournalAlimentaire,
        "journal_id",
        owner_field="utilisateur_id",
        create_schema=JournalAlimentaireCreate,
        update_schema=JournalAlimentaireUpdate,
    ),
    ResourceConfig("/executions-etl", models.ExecutionEtl, "execution_id"),
    ResourceConfig("/lots-donnees", models.LotDonnees, "lot_id"),
    ResourceConfig("/enregistrements-bruts", models.EnregistrementBrut, "enregistrement_id"),
    ResourceConfig("/stg-imports", models.StgImport, "stg_id"),
    ResourceConfig("/controles-qualite-donnees", models.ControleQualiteDonnee, "controle_id"),
]

for resource in RESOURCES:
    api_router.include_router(create_crud_router(resource))
