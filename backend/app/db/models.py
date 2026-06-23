from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.mysql import BIGINT as MySQLBigInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

MYSQL_ID_TYPE = BigInteger().with_variant(Integer, "sqlite").with_variant(MySQLBigInteger(unsigned=True), "mysql").with_variant(MySQLBigInteger(unsigned=True), "mariadb")


class TimestampMixin:
    cree_le: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Organisation(Base, TimestampMixin):
    __tablename__ = "organisation"

    organisation_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nom: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    adresse: Mapped[str | None] = mapped_column(Text)
    image_path: Mapped[str | None] = mapped_column(String(500))

    utilisateurs: Mapped[list[Utilisateur]] = relationship(back_populates="organisation")  # type: ignore[name-defined]


class SourceDonnees(Base, TimestampMixin):
    __tablename__ = "source_donnees"

    source_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nom: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    type_source: Mapped[str | None] = mapped_column(String(80))
    format_source: Mapped[str | None] = mapped_column(String(80))
    actif: Mapped[bool] = mapped_column(Boolean, default=True)


class RegleQualite(Base):
    __tablename__ = "regle_qualite"
    __table_args__ = (UniqueConstraint("code_regle", name="uq_regle_qualite_code"),)

    regle_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entite: Mapped[str] = mapped_column(String(80), nullable=False)
    nom_champ: Mapped[str | None] = mapped_column(String(120))
    code_regle: Mapped[str] = mapped_column(String(120), nullable=False)
    type_regle: Mapped[str | None] = mapped_column(String(80))
    severite: Mapped[str | None] = mapped_column(String(30))
    description: Mapped[str | None] = mapped_column(Text)
    actif: Mapped[bool] = mapped_column(Boolean, default=True)


class Utilisateur(Base):
    __tablename__ = "utilisateur"
    __table_args__ = (
        UniqueConstraint("email", name="uq_utilisateur_email"),
        UniqueConstraint("nom_utilisateur", name="uq_utilisateur_nom_utilisateur"),
        UniqueConstraint("gym_external_id", name="uq_utilisateur_gym_external_id"),
        UniqueConstraint("sleep_external_id", name="uq_utilisateur_sleep_external_id"),
    )

    utilisateur_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organisation_id: Mapped[int | None] = mapped_column(ForeignKey("organisation.organisation_id"), nullable=True)
    gym_external_id: Mapped[str | None] = mapped_column(String(120))
    sleep_external_id: Mapped[str | None] = mapped_column(String(120))
    nom_utilisateur: Mapped[str] = mapped_column(String(120), nullable=False)
    prenom: Mapped[str | None] = mapped_column(String(120))
    nom: Mapped[str | None] = mapped_column(String(120))
    email: Mapped[str | None] = mapped_column(String(255))
    date_naissance: Mapped[date | None] = mapped_column(Date)
    genre: Mapped[str] = mapped_column(String(40), default="Inconnu", nullable=False)
    taille_cm: Mapped[float | None] = mapped_column(Float)
    photo_profil_path: Mapped[str | None] = mapped_column(String(500))
    niveau_activite: Mapped[str | None] = mapped_column(String(80))
    niveau_sportif: Mapped[str | None] = mapped_column(String(80))
    allergies_json: Mapped[str | None] = mapped_column(Text)
    regime_alimentaire: Mapped[str | None] = mapped_column(String(120))
    preferences_alimentaires_json: Mapped[str | None] = mapped_column(Text)
    aliments_evites_json: Mapped[str | None] = mapped_column(Text)
    budget_alimentaire: Mapped[str | None] = mapped_column(String(80))
    equipements_json: Mapped[str | None] = mapped_column(Text)
    contraintes_sante_json: Mapped[str | None] = mapped_column(Text)
    preferences_sportives_json: Mapped[str | None] = mapped_column(Text)
    frequence_seances_hebdo: Mapped[int | None] = mapped_column(Integer)
    duree_seance_min: Mapped[int | None] = mapped_column(Integer)
    onboarding_complete: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    onboarding_complete_le: Mapped[datetime | None] = mapped_column(DateTime)
    role: Mapped[str] = mapped_column(String(30), default="UTILISATEUR")
    statut: Mapped[str] = mapped_column(String(30), default="ACTIF")
    mot_de_passe_hash: Mapped[str | None] = mapped_column(String(255))
    cree_le: Mapped[datetime | None] = mapped_column(DateTime)
    modifie_le: Mapped[datetime | None] = mapped_column(DateTime)

    organisation: Mapped[Organisation | None] = relationship(back_populates="utilisateurs")


class ObjectifUtilisateur(Base, TimestampMixin):
    __tablename__ = "objectif_utilisateur"

    objectif_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    utilisateur_id: Mapped[int] = mapped_column(ForeignKey("utilisateur.utilisateur_id"), nullable=False)
    type_objectif: Mapped[str] = mapped_column(String(80), nullable=False)
    poids_cible_kg: Mapped[float | None] = mapped_column(Float)
    date_debut: Mapped[date | None] = mapped_column(Date)
    date_fin: Mapped[date | None] = mapped_column(Date)
    actif_unique: Mapped[bool] = mapped_column(Boolean, default=True)
    statut_objectif: Mapped[str | None] = mapped_column(String(30), default="EN_COURS")
    commentaire: Mapped[str | None] = mapped_column(Text)


class ProgressionPhoto(Base, TimestampMixin):
    __tablename__ = "progression_photo"

    photo_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    utilisateur_id: Mapped[int] = mapped_column(ForeignKey("utilisateur.utilisateur_id"), nullable=False)
    objectif_id: Mapped[int | None] = mapped_column(ForeignKey("objectif_utilisateur.objectif_id"))
    type_photo: Mapped[str | None] = mapped_column(String(40))
    image_path: Mapped[str] = mapped_column(String(500), nullable=False)
    prise_le: Mapped[date | None] = mapped_column(Date)


class MesureBiometrique(Base, TimestampMixin):
    __tablename__ = "mesure_biometrique"

    mesure_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    utilisateur_id: Mapped[int] = mapped_column(ForeignKey("utilisateur.utilisateur_id"), nullable=False)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("source_donnees.source_id"))
    lot_id: Mapped[int | None] = mapped_column(ForeignKey("lot_donnees.lot_id"))
    mesure_le: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    age_source: Mapped[int | None] = mapped_column(Integer)
    genre_source: Mapped[str | None] = mapped_column(String(40))
    poids_kg: Mapped[float | None] = mapped_column(Float)
    taille_cm: Mapped[float | None] = mapped_column(Float)
    imc: Mapped[float | None] = mapped_column(Float)
    taux_masse_grasse: Mapped[float | None] = mapped_column(Float)
    bpm_repos: Mapped[int | None] = mapped_column(Integer)
    bpm_moyen: Mapped[int | None] = mapped_column(Integer)
    bpm_max: Mapped[int | None] = mapped_column(Integer)
    eau_l: Mapped[float | None] = mapped_column(Float)


class MesureSommeilSante(Base, TimestampMixin):
    __tablename__ = "mesure_sommeil_sante"

    mesure_sommeil_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    utilisateur_id: Mapped[int] = mapped_column(ForeignKey("utilisateur.utilisateur_id"), nullable=False)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("source_donnees.source_id"))
    lot_id: Mapped[int | None] = mapped_column(ForeignKey("lot_donnees.lot_id"))
    mesure_le: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    person_id_source: Mapped[str | None] = mapped_column(String(120))
    genre_source: Mapped[str | None] = mapped_column(String(40))
    age_source: Mapped[int | None] = mapped_column(Integer)
    profession: Mapped[str | None] = mapped_column(String(160))
    duree_sommeil_h: Mapped[float | None] = mapped_column(Float)
    qualite_sommeil_score: Mapped[int | None] = mapped_column(Integer)
    activite_physique_min_jour: Mapped[int | None] = mapped_column(Integer)
    stress_score: Mapped[int | None] = mapped_column(Integer)
    categorie_imc_source: Mapped[str | None] = mapped_column(String(80))
    tension_arterielle_brut: Mapped[str | None] = mapped_column(String(40))
    tension_systolique: Mapped[int | None] = mapped_column(Integer)
    tension_diastolique: Mapped[int | None] = mapped_column(Integer)
    frequence_cardiaque_bpm: Mapped[int | None] = mapped_column(Integer)
    pas_jour: Mapped[int | None] = mapped_column(Integer)
    trouble_sommeil_brut: Mapped[str | None] = mapped_column(String(120))
    trouble_sommeil_normalise: Mapped[str | None] = mapped_column(String(120))


class Exercice(Base, TimestampMixin):
    __tablename__ = "exercice"

    exercice_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("source_donnees.source_id"))
    external_id: Mapped[str | None] = mapped_column(String(120), unique=True)
    nom: Mapped[str] = mapped_column(String(255), nullable=False)
    gif_180_path: Mapped[str | None] = mapped_column(String(500))
    gif_360_path: Mapped[str | None] = mapped_column(String(500))
    gif_720_path: Mapped[str | None] = mapped_column(String(500))
    gif_1080_path: Mapped[str | None] = mapped_column(String(500))
    body_part_principale: Mapped[str | None] = mapped_column(String(120))
    muscle_cible_principal: Mapped[str | None] = mapped_column(String(120))
    equipement_principal: Mapped[str | None] = mapped_column(String(120))
    body_parts_json: Mapped[str | None] = mapped_column(Text)
    target_muscles_json: Mapped[str | None] = mapped_column(Text)
    secondary_muscles_json: Mapped[str | None] = mapped_column(Text)
    equipments_json: Mapped[str | None] = mapped_column(Text)
    instructions_json: Mapped[str | None] = mapped_column(Text)


class SeanceEntrainement(Base, TimestampMixin):
    __tablename__ = "seance_entrainement"

    seance_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    utilisateur_id: Mapped[int] = mapped_column(ForeignKey("utilisateur.utilisateur_id"), nullable=False)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("source_donnees.source_id"))
    lot_id: Mapped[int | None] = mapped_column(ForeignKey("lot_donnees.lot_id"))
    date_seance: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    type_entrainement: Mapped[str | None] = mapped_column(String(80))
    duree_seance_min: Mapped[int | None] = mapped_column(Integer)
    calories_brulees_total: Mapped[float | None] = mapped_column(Float)
    frequence_entrainement_j_sem: Mapped[int | None] = mapped_column(Integer)
    niveau_experience: Mapped[str | None] = mapped_column(String(80))
    eau_l: Mapped[float | None] = mapped_column(Float)


class SeanceExercice(Base, TimestampMixin):
    __tablename__ = "seance_exercice"

    seance_exercice_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    seance_id: Mapped[int] = mapped_column(ForeignKey("seance_entrainement.seance_id"), nullable=False)
    exercice_id: Mapped[int] = mapped_column(ForeignKey("exercice.exercice_id"), nullable=False)
    ordre_exercice: Mapped[int | None] = mapped_column(Integer)
    series_nb: Mapped[int | None] = mapped_column(Integer)
    repetitions_nb: Mapped[int | None] = mapped_column(Integer)
    charge_kg: Mapped[float | None] = mapped_column(Float)
    duree_min: Mapped[float | None] = mapped_column(Float)
    calories_brulees_estimees: Mapped[float | None] = mapped_column(Float)
    commentaire: Mapped[str | None] = mapped_column(String(255))


class CoachPostureSession(Base):
    __tablename__ = "coach_posture_session"

    coach_posture_id: Mapped[int] = mapped_column(MYSQL_ID_TYPE, primary_key=True, autoincrement=True)
    utilisateur_id: Mapped[int] = mapped_column(MYSQL_ID_TYPE, ForeignKey("utilisateur.utilisateur_id"), nullable=False, index=True)
    exercice_code: Mapped[str] = mapped_column(String(80), nullable=False)
    exercice_nom: Mapped[str] = mapped_column(String(120), nullable=False)
    type_exercice: Mapped[str] = mapped_column(String(20), nullable=False)
    statut_posture: Mapped[str] = mapped_column(String(40), nullable=False)
    score_alignement: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reps: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reps_in_current_set: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sets_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    hold_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    best_hold_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    validated_holds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    detected_errors_json: Mapped[str | None] = mapped_column(Text)
    feedback_json: Mapped[str | None] = mapped_column(Text)
    snapshot_path: Mapped[str | None] = mapped_column(String(500))
    source_page: Mapped[str] = mapped_column(String(80), default="coach_posture", nullable=False)
    valide_le: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    cree_le: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class Aliment(Base, TimestampMixin):
    __tablename__ = "aliment"

    aliment_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("source_donnees.source_id"))
    nom: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    categorie: Mapped[str | None] = mapped_column(String(120))
    calories_kcal: Mapped[float | None] = mapped_column(Float)
    proteines_g: Mapped[float | None] = mapped_column(Float)
    glucides_g: Mapped[float | None] = mapped_column(Float)
    lipides_g: Mapped[float | None] = mapped_column(Float)
    fibres_g: Mapped[float | None] = mapped_column(Float)
    sucres_g: Mapped[float | None] = mapped_column(Float)
    sodium_mg: Mapped[float | None] = mapped_column(Float)
    cholesterol_mg: Mapped[float | None] = mapped_column(Float)


class Plat(Base, TimestampMixin):
    __tablename__ = "plat"

    plat_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    utilisateur_id: Mapped[int] = mapped_column(ForeignKey("utilisateur.utilisateur_id"), nullable=False)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("source_donnees.source_id"))
    lot_id: Mapped[int | None] = mapped_column(ForeignKey("lot_donnees.lot_id"))
    consomme_le: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    type_repas: Mapped[str | None] = mapped_column(String(80))
    nom_plat: Mapped[str | None] = mapped_column(String(255))
    calories_totales_kcal: Mapped[float | None] = mapped_column(Float)


class JournalAlimentaire(Base, TimestampMixin):
    __tablename__ = "journal_alimentaire"

    journal_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    utilisateur_id: Mapped[int] = mapped_column(ForeignKey("utilisateur.utilisateur_id"), nullable=False)
    plat_id: Mapped[int | None] = mapped_column(ForeignKey("plat.plat_id"))
    aliment_id: Mapped[int | None] = mapped_column(ForeignKey("aliment.aliment_id"))
    source_id: Mapped[int | None] = mapped_column(ForeignKey("source_donnees.source_id"))
    lot_id: Mapped[int | None] = mapped_column(ForeignKey("lot_donnees.lot_id"))
    consomme_le: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    type_repas: Mapped[str | None] = mapped_column(String(80))
    aliment_nom_libre: Mapped[str | None] = mapped_column(String(255))
    quantite: Mapped[float | None] = mapped_column(Float)
    unite_quantite: Mapped[str | None] = mapped_column(String(40))
    calories_kcal: Mapped[float | None] = mapped_column(Float)
    eau_ml: Mapped[float | None] = mapped_column(Float)


class ExecutionEtl(Base):
    __tablename__ = "execution_etl"

    execution_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("source_donnees.source_id"), nullable=False)
    statut: Mapped[str] = mapped_column(String(40), nullable=False)
    demarre_le: Mapped[datetime | None] = mapped_column(DateTime)
    termine_le: Mapped[datetime | None] = mapped_column(DateTime)
    lignes_lues: Mapped[int | None] = mapped_column(Integer)
    lignes_valides: Mapped[int | None] = mapped_column(Integer)
    lignes_invalides: Mapped[int | None] = mapped_column(Integer)
    nb_doublons_supprimes: Mapped[int | None] = mapped_column(Integer)
    nb_valeurs_corrigees: Mapped[int | None] = mapped_column(Integer)
    nb_rejets: Mapped[int | None] = mapped_column(Integer)
    taux_qualite: Mapped[float | None] = mapped_column(Float)
    message: Mapped[str | None] = mapped_column(Text)


class LotDonnees(Base):
    __tablename__ = "lot_donnees"

    lot_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    execution_id: Mapped[int] = mapped_column(ForeignKey("execution_etl.execution_id"), nullable=False)
    source_id: Mapped[int] = mapped_column(ForeignKey("source_donnees.source_id"), nullable=False)
    nom_lot: Mapped[str] = mapped_column(String(255), nullable=False)
    statut: Mapped[str] = mapped_column(String(40), nullable=False)
    cree_par_utilisateur_id: Mapped[int | None] = mapped_column(ForeignKey("utilisateur.utilisateur_id"))
    valide_par_utilisateur_id: Mapped[int | None] = mapped_column(ForeignKey("utilisateur.utilisateur_id"))
    valide_le: Mapped[datetime | None] = mapped_column(DateTime)
    commentaire_validation: Mapped[str | None] = mapped_column(Text)
    cree_le: Mapped[datetime | None] = mapped_column(DateTime)


class EnregistrementBrut(Base, TimestampMixin):
    __tablename__ = "enregistrement_brut"

    enregistrement_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lot_id: Mapped[int] = mapped_column(ForeignKey("lot_donnees.lot_id"), nullable=False)
    entite: Mapped[str] = mapped_column(String(80), nullable=False)
    ref_externe: Mapped[str | None] = mapped_column(String(160))
    payload_json: Mapped[str | None] = mapped_column(Text)


class StgImport(Base, TimestampMixin):
    __tablename__ = "stg_import"

    stg_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lot_id: Mapped[int] = mapped_column(ForeignKey("lot_donnees.lot_id"), nullable=False)
    entite: Mapped[str] = mapped_column(String(80), nullable=False)
    ref_externe: Mapped[str | None] = mapped_column(String(160))
    source_payload_json: Mapped[str | None] = mapped_column(Text)
    payload_normalise_json: Mapped[str | None] = mapped_column(Text)
    est_parseable: Mapped[bool | None] = mapped_column(Boolean)
    statut_validation: Mapped[str | None] = mapped_column(String(80))
    code_rejet_potentiel: Mapped[str | None] = mapped_column(String(120))


class ControleQualiteDonnee(Base, TimestampMixin):
    __tablename__ = "controle_qualite_donnee"

    controle_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    execution_id: Mapped[int] = mapped_column(ForeignKey("execution_etl.execution_id"), nullable=False)
    lot_id: Mapped[int | None] = mapped_column(ForeignKey("lot_donnees.lot_id"))
    regle_id: Mapped[int | None] = mapped_column(ForeignKey("regle_qualite.regle_id"))
    entite: Mapped[str] = mapped_column(String(80), nullable=False)
    ref_externe: Mapped[str | None] = mapped_column(String(160))
    ref_ligne: Mapped[str | None] = mapped_column(String(160))
    nom_champ: Mapped[str | None] = mapped_column(String(120))
    valeur_observee: Mapped[str | None] = mapped_column(Text)
    valeur_corrigee: Mapped[str | None] = mapped_column(Text)
    payload_json: Mapped[str | None] = mapped_column(Text)
    niveau: Mapped[str | None] = mapped_column(String(40))
    type_controle: Mapped[str | None] = mapped_column(String(80))
    decision_finale: Mapped[str | None] = mapped_column(String(80))
    est_bloquant: Mapped[bool | None] = mapped_column(Boolean)
    code_controle: Mapped[str | None] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    etape_pipeline: Mapped[str | None] = mapped_column(String(80))
