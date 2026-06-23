from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

from sqlalchemy import func, inspect, select, text
from sqlalchemy.orm import Session

from app.core.security import hash_password_pbkdf2_sha256, verify_password
from app.db.models import (
    Aliment,
    Exercice,
    JournalAlimentaire,
    MesureBiometrique,
    MesureSommeilSante,
    ObjectifUtilisateur,
    Organisation,
    Plat,
    ProgressionPhoto,
    SeanceEntrainement,
    SeanceExercice,
    Utilisateur,
)

logger = logging.getLogger(__name__)

DEMO_ACCOUNTS: tuple[tuple[str, str], ...] = (
    ("user", "UTILISATEUR"),
    ("admin", "ADMIN"),
    ("superadmin", "SUPER_ADMIN"),
)


def ensure_demo_accounts(db: Session) -> None:
    """Ensure the three local demo accounts exist with the expected roles.

    The demo password is intentionally derived at runtime from the username so
    there is no stored clear-text password or copied hash in the codebase.
    """

    organisation = db.execute(
        select(Organisation).order_by(Organisation.organisation_id).limit(1)
    ).scalar_one_or_none()
    if organisation is None:
        organisation = Organisation(
            nom="HealthAI Demo",
            adresse="Organisation de demonstration locale",
            cree_le=datetime.utcnow(),
        )
        db.add(organisation)
        db.flush()

    ensure_objectif_status_column(db)
    changed = False
    for username, role in DEMO_ACCOUNTS:
        account_changed = False
        user = db.execute(
            select(Utilisateur)
            .where(Utilisateur.nom_utilisateur == username)
            .order_by(Utilisateur.utilisateur_id)
            .limit(1)
        ).scalar_one_or_none()
        if user is None:
            user = Utilisateur(
                organisation_id=organisation.organisation_id,
                nom_utilisateur=username,
                prenom=username.title(),
                nom="Demo",
                email=f"{username}@healthai.local",
                genre="Inconnu",
                role=role,
                statut="ACTIF",
                mot_de_passe_hash=hash_password_pbkdf2_sha256(username),
                cree_le=datetime.utcnow(),
                modifie_le=datetime.utcnow(),
            )
            db.add(user)
            changed = True
            continue

        if user.role != role:
            user.role = role
            account_changed = True
        if user.statut != "ACTIF":
            user.statut = "ACTIF"
            account_changed = True
        if not verify_password(username, user.mot_de_passe_hash):
            user.mot_de_passe_hash = hash_password_pbkdf2_sha256(username)
            account_changed = True
        if user.email is None:
            user.email = f"{username}@healthai.local"
            account_changed = True
        if user.organisation_id is None:
            user.organisation_id = organisation.organisation_id
            account_changed = True
        if account_changed:
            user.modifie_le = datetime.utcnow()
            changed = True

    if changed:
        db.commit()
        logger.info("Demo accounts ensured")

    demo_user = db.execute(select(Utilisateur).where(Utilisateur.nom_utilisateur == "user").limit(1)).scalar_one_or_none()
    if demo_user is not None:
        ensure_user_demo_data(db, demo_user.utilisateur_id)


def ensure_objectif_status_column(db: Session) -> None:
    columns = {col["name"] for col in inspect(db.bind).get_columns("objectif_utilisateur")}
    if "statut_objectif" not in columns:
        db.execute(text("ALTER TABLE objectif_utilisateur ADD COLUMN statut_objectif VARCHAR(30) DEFAULT 'EN_COURS'"))
        db.commit()


def ensure_user_demo_data(db: Session, utilisateur_id: int) -> None:
    now = datetime.utcnow()
    today = date.today()
    biometrie_count = db.scalar(
        select(func.count(MesureBiometrique.mesure_id)).where(MesureBiometrique.utilisateur_id == utilisateur_id)
    ) or 0
    if biometrie_count < 8:
        for idx in range(int(biometrie_count), 8):
            when = now - timedelta(days=(7 - idx) * 4)
            weight = 86.0 - idx * 0.8
            height = 178.0
            db.add(MesureBiometrique(
                utilisateur_id=utilisateur_id,
                mesure_le=when,
                poids_kg=weight,
                taille_cm=height,
                imc=round(weight / ((height / 100) ** 2), 2),
                taux_masse_grasse=24.0 - idx * 0.4,
                bpm_repos=68 - idx // 2,
                bpm_moyen=118 + idx,
                bpm_max=156 + idx,
                eau_l=2.0 + idx * 0.05,
                cree_le=when,
            ))
            db.add(MesureSommeilSante(
                utilisateur_id=utilisateur_id,
                mesure_le=when,
                duree_sommeil_h=6.3 + idx * 0.15,
                qualite_sommeil_score=62 + idx * 3,
                stress_score=max(18, 55 - idx * 4),
                activite_physique_min_jour=25 + idx * 5,
                frequence_cardiaque_bpm=64 - idx // 2,
                pas_jour=5500 + idx * 650,
                tension_systolique=124 - idx,
                tension_diastolique=82 - idx // 2,
                trouble_sommeil_normalise=None,
                cree_le=when,
            ))

    exercices = db.execute(select(Exercice).order_by(Exercice.exercice_id).limit(12)).scalars().all()
    if len(exercices) >= 3:
        seances = db.execute(
            select(SeanceEntrainement)
            .where(SeanceEntrainement.utilisateur_id == utilisateur_id)
            .order_by(SeanceEntrainement.date_seance.asc(), SeanceEntrainement.seance_id.asc())
        ).scalars().all()
        if len(seances) < 8:
            workout_types = ["MUSCULATION", "CARDIO", "MOBILITE", "HIIT"]
            for idx in range(len(seances), 8):
                when = now - timedelta(days=(7 - idx) * 4)
                seance = SeanceEntrainement(
                    utilisateur_id=utilisateur_id,
                    date_seance=when,
                    type_entrainement=workout_types[idx % len(workout_types)],
                    duree_seance_min=35 + idx * 4,
                    calories_brulees_total=220 + idx * 35,
                    frequence_entrainement_j_sem=3,
                    niveau_experience=["DEBUTANT", "INTERMEDIAIRE", "AVANCE"][idx % 3],
                    eau_l=0.8 + idx * 0.1,
                    cree_le=when,
                )
                db.add(seance)
                db.flush()
                for ex_idx in range(3):
                    exercice = exercices[(idx + ex_idx) % len(exercices)]
                    db.add(SeanceExercice(
                        seance_id=seance.seance_id,
                        exercice_id=exercice.exercice_id,
                        ordre_exercice=ex_idx + 1,
                        series_nb=3 + (ex_idx % 2),
                        repetitions_nb=10 + ex_idx * 2,
                        charge_kg=12.5 + idx * 2 + ex_idx * 3,
                        duree_min=8 + ex_idx * 4,
                        calories_brulees_estimees=55 + idx * 8 + ex_idx * 10,
                        commentaire=f"Bloc demo {ex_idx + 1}",
                        cree_le=when,
                    ))
                seances.append(seance)
        else:
            for idx, seance in enumerate(seances):
                existing_lines = db.scalar(
                    select(func.count(SeanceExercice.seance_exercice_id)).where(SeanceExercice.seance_id == seance.seance_id)
                ) or 0
                if existing_lines >= 2:
                    continue
                for ex_idx in range(int(existing_lines), 3):
                    exercice = exercices[(idx + ex_idx) % len(exercices)]
                    db.add(SeanceExercice(
                        seance_id=seance.seance_id,
                        exercice_id=exercice.exercice_id,
                        ordre_exercice=ex_idx + 1,
                        series_nb=3,
                        repetitions_nb=10 + ex_idx * 2,
                        charge_kg=15 + ex_idx * 4,
                        duree_min=10 + ex_idx * 3,
                        calories_brulees_estimees=70 + ex_idx * 12,
                        commentaire="Ajout demo auto",
                        cree_le=seance.date_seance,
                    ))

    aliments = db.execute(select(Aliment).order_by(Aliment.aliment_id).limit(24)).scalars().all()
    if aliments:
        meal_types = ["PetitDejeuner", "Dejeuner", "Diner"]
        meal_names = [
            "Bowl yaourt et fruits",
            "Poulet riz legumes",
            "Saumon quinoa",
            "Porridge energie",
            "Wrap dinde crudites",
            "Pates bolognaise maison",
            "Omelette epinards",
            "Salade complete",
        ]
        plats = db.execute(
            select(Plat)
            .where(Plat.utilisateur_id == utilisateur_id)
            .order_by(Plat.consomme_le.asc(), Plat.plat_id.asc())
        ).scalars().all()
        if len(plats) < 8:
            for idx in range(len(plats), 8):
                when = now - timedelta(days=(7 - idx) * 4)
                plat = Plat(
                    utilisateur_id=utilisateur_id,
                    consomme_le=when,
                    type_repas=meal_types[idx % len(meal_types)],
                    nom_plat=meal_names[idx % len(meal_names)],
                    calories_totales_kcal=0,
                    cree_le=when,
                )
                db.add(plat)
                db.flush()
                plats.append(plat)
        for idx, plat in enumerate(plats[:8]):
            existing_lines = db.execute(
                select(JournalAlimentaire)
                .where(JournalAlimentaire.plat_id == plat.plat_id)
                .order_by(JournalAlimentaire.journal_id.asc())
            ).scalars().all()
            if len(existing_lines) >= 2:
                total = sum(float(line.calories_kcal or 0) for line in existing_lines)
                plat.calories_totales_kcal = round(total, 2)
                continue
            for line_idx in range(len(existing_lines), 3):
                aliment = aliments[(idx * 3 + line_idx) % len(aliments)]
                quantity = [120, 150, 80, 200][(idx + line_idx) % 4]
                factor = quantity / 100
                calories = round(float(aliment.calories_kcal or 0) * factor, 2)
                db.add(JournalAlimentaire(
                    utilisateur_id=utilisateur_id,
                    plat_id=plat.plat_id,
                    aliment_id=aliment.aliment_id,
                    consomme_le=plat.consomme_le,
                    type_repas=plat.type_repas,
                    aliment_nom_libre=aliment.nom,
                    quantite=quantity,
                    unite_quantite="g",
                    calories_kcal=calories,
                    eau_ml=round(quantity * 0.6, 2),
                    cree_le=plat.consomme_le,
                ))
            db.flush()
            total = db.scalar(
                select(func.coalesce(func.sum(JournalAlimentaire.calories_kcal), 0)).where(JournalAlimentaire.plat_id == plat.plat_id)
            ) or 0
            plat.calories_totales_kcal = round(float(total), 2)

    desired_objectives = [
        ("PERTE_POIDS", "REUSSI", today - timedelta(days=120), today - timedelta(days=85), False, "Objectif atteint."),
        ("GAIN_MUSCLE", "ECHOUE", today - timedelta(days=80), today - timedelta(days=55), False, "Priorite mise sur le cardio."),
        ("SOMMEIL", "ANNULE", today - timedelta(days=50), today - timedelta(days=35), False, "Objectif interrompu."),
        ("MAINTIEN_FORME", "EN_COURS", today - timedelta(days=14), None, True, "Tenir 4 seances par semaine."),
    ]
    existing_goal_types = {
        row[0]
        for row in db.execute(
            select(ObjectifUtilisateur.type_objectif).where(ObjectifUtilisateur.utilisateur_id == utilisateur_id)
        ).all()
        if row[0]
    }
    active_goal = db.execute(
        select(ObjectifUtilisateur)
        .where(
            ObjectifUtilisateur.utilisateur_id == utilisateur_id,
            ObjectifUtilisateur.actif_unique.is_(True),
        )
        .order_by(ObjectifUtilisateur.objectif_id.desc())
        .limit(1)
    ).scalar_one_or_none()
    for type_objectif, statut, debut, fin, active, commentaire in desired_objectives:
        if type_objectif in existing_goal_types:
            continue
        if active and active_goal is not None:
            active = False
            fin = fin or today
            statut = "REUSSI" if statut == "EN_COURS" else statut
        db.add(ObjectifUtilisateur(
            utilisateur_id=utilisateur_id,
            type_objectif=type_objectif,
            date_debut=debut,
            date_fin=fin,
            actif_unique=active,
            statut_objectif=statut,
            commentaire=commentaire,
            cree_le=now,
        ))
        if active:
            active_goal = True

    has_active_goal = db.execute(
        select(ObjectifUtilisateur)
        .where(
            ObjectifUtilisateur.utilisateur_id == utilisateur_id,
            ObjectifUtilisateur.actif_unique.is_(True),
        )
        .limit(1)
    ).scalar_one_or_none()
    if has_active_goal is None:
        db.add(ObjectifUtilisateur(
            utilisateur_id=utilisateur_id,
            type_objectif="MAINTIEN_FORME",
            date_debut=today - timedelta(days=7),
            date_fin=None,
            actif_unique=True,
            statut_objectif="EN_COURS",
            commentaire="Objectif actif demo",
            cree_le=now,
        ))

    photo_types = {
        row[0]
        for row in db.execute(
            select(ProgressionPhoto.type_photo).where(ProgressionPhoto.utilisateur_id == utilisateur_id)
        ).all()
        if row[0]
    }
    if "BEFORE" not in photo_types:
        db.add(ProgressionPhoto(
            utilisateur_id=utilisateur_id,
            type_photo="BEFORE",
            image_path="before1.png",
            prise_le=today - timedelta(days=28),
            cree_le=now,
        ))
    if "AFTER" not in photo_types:
        db.add(ProgressionPhoto(
            utilisateur_id=utilisateur_id,
            type_photo="AFTER",
            image_path="after1.png",
            prise_le=today - timedelta(days=1),
            cree_le=now,
        ))
    db.commit()
    logger.info("Demo user data ensured")
