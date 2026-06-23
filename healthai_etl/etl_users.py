from __future__ import annotations

import csv
import os
import random
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from etl_common import (
    ExecutionStats,
    build_random_identity,
    create_execution,
    create_lot,
    fetch_one,
    finish_execution,
    get_engine,
    normalize_gender_fr,
    seed_default_organisations,
    seed_default_sources,
    set_lot_status,
    to_int,
)


def upsert_user(conn, payload: dict) -> int:
    row = None
    if payload.get("gym_external_id"):
        row = fetch_one(conn, "SELECT utilisateur_id FROM utilisateur WHERE gym_external_id = :v LIMIT 1", {"v": payload["gym_external_id"]})
    if row is None and payload.get("sleep_external_id"):
        row = fetch_one(conn, "SELECT utilisateur_id FROM utilisateur WHERE sleep_external_id = :v LIMIT 1", {"v": payload["sleep_external_id"]})
    if row is None:
        row = fetch_one(conn, "SELECT utilisateur_id FROM utilisateur WHERE nom_utilisateur = :u LIMIT 1", {"u": payload["nom_utilisateur"]})

    if row:
        utilisateur_id = int(row["utilisateur_id"])
        conn.execute(
            text(
                """
                UPDATE utilisateur
                   SET organisation_id = :organisation_id,
                       gym_external_id = COALESCE(:gym_external_id, gym_external_id),
                       sleep_external_id = COALESCE(:sleep_external_id, sleep_external_id),
                       prenom = :prenom,
                       nom = :nom,
                       email = :email,
                       date_naissance = :date_naissance,
                       genre = :genre,
                       taille_cm = :taille_cm,
                       role = :role,
                       statut = :statut,
                       mot_de_passe_hash = :mot_de_passe_hash,
                       modifie_le = NOW()
                 WHERE utilisateur_id = :utilisateur_id
                """
            ),
            {**payload, "utilisateur_id": utilisateur_id},
        )
        return utilisateur_id

    result = conn.execute(
        text(
            """
            INSERT INTO utilisateur (
              organisation_id, gym_external_id, sleep_external_id, nom_utilisateur,
              prenom, nom, email, date_naissance, genre, taille_cm,
              role, statut, mot_de_passe_hash, cree_le, modifie_le
            ) VALUES (
              :organisation_id, :gym_external_id, :sleep_external_id, :nom_utilisateur,
              :prenom, :nom, :email, :date_naissance, :genre, :taille_cm,
              :role, :statut, :mot_de_passe_hash, NOW(), NOW()
            )
            """
        ),
        payload,
    )
    return int(result.lastrowid)


def main() -> None:
    gym_csv = os.getenv("GYM_CSV")
    sleep_csv = os.getenv("SLEEP_CSV")
    admin_count = int(os.getenv("ADMIN_COUNT", "10"))
    super_admin_count = int(os.getenv("SUPER_ADMIN_COUNT", "3"))
    export_csv = Path(os.getenv("USERS_EXPORT_CSV", str(Path(__file__).resolve().parent / "exports" / "generated_users_credentials.csv")))
    export_csv.parent.mkdir(parents=True, exist_ok=True)

    if not gym_csv or not Path(gym_csv).exists():
        raise RuntimeError("GYM_CSV manquant ou introuvable pour la creation des utilisateurs")

    engine = get_engine()
    stats = ExecutionStats()
    rng = random.Random(20260430)

    with engine.begin() as conn:
        source_ids = seed_default_sources(conn)
        org_ids = list(seed_default_organisations(conn).values())
        source_id = source_ids["Synthetic User Seed"]
        execution_id = create_execution(conn, source_id)

    try:
        gym_df = pd.read_csv(gym_csv).reset_index(drop=True)
        sleep_count = 0
        if sleep_csv and Path(sleep_csv).exists():
            sleep_df = pd.read_csv(sleep_csv)
            sleep_count = len(sleep_df)

        stats.lignes_lues = len(gym_df) + admin_count + super_admin_count

        with engine.begin() as conn:
            lot_id = create_lot(conn, execution_id, source_id, f"users_seed_{pd.Timestamp.now():%Y%m%d_%H%M%S}")
            set_lot_status(conn, lot_id, "VALIDE")

            with export_csv.open("w", newline="", encoding="utf-8") as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=["role", "utilisateur_id", "pseudonyme", "prenom", "nom", "email", "mot_de_passe_demo"])
                writer.writeheader()

                for _ in range(super_admin_count):
                    identity = build_random_identity(rng, conn, age=rng.randint(28, 58), genre="Inconnu")
                    payload = {
                        "organisation_id": rng.choice(org_ids),
                        "gym_external_id": None,
                        "sleep_external_id": None,
                        "nom_utilisateur": identity["nom_utilisateur"],
                        "prenom": identity["prenom"],
                        "nom": identity["nom"],
                        "email": identity["email"],
                        "date_naissance": identity["date_naissance"],
                        "genre": "Inconnu",
                        "taille_cm": None,
                        "role": "SUPER_ADMIN",
                        "statut": "ACTIF",
                        "mot_de_passe_hash": identity["mot_de_passe_hash"],
                    }
                    uid = upsert_user(conn, payload)
                    writer.writerow({
                        "role": "SUPER_ADMIN",
                        "utilisateur_id": uid,
                        "pseudonyme": payload["nom_utilisateur"],
                        "prenom": payload["prenom"],
                        "nom": payload["nom"],
                        "email": payload["email"],
                        "mot_de_passe_demo": identity["mot_de_passe_clair"],
                    })
                    stats.lignes_valides += 1

                for _ in range(admin_count):
                    identity = build_random_identity(rng, conn, age=rng.randint(24, 60), genre="Inconnu")
                    payload = {
                        "organisation_id": rng.choice(org_ids),
                        "gym_external_id": None,
                        "sleep_external_id": None,
                        "nom_utilisateur": identity["nom_utilisateur"],
                        "prenom": identity["prenom"],
                        "nom": identity["nom"],
                        "email": identity["email"],
                        "date_naissance": identity["date_naissance"],
                        "genre": "Inconnu",
                        "taille_cm": None,
                        "role": "ADMIN",
                        "statut": "ACTIF",
                        "mot_de_passe_hash": identity["mot_de_passe_hash"],
                    }
                    uid = upsert_user(conn, payload)
                    writer.writerow({
                        "role": "ADMIN",
                        "utilisateur_id": uid,
                        "pseudonyme": payload["nom_utilisateur"],
                        "prenom": payload["prenom"],
                        "nom": payload["nom"],
                        "email": payload["email"],
                        "mot_de_passe_demo": identity["mot_de_passe_clair"],
                    })
                    stats.lignes_valides += 1

                for row_idx, row in enumerate(gym_df.to_dict(orient="records"), start=1):
                    age = to_int(row.get("Age"))
                    gender = normalize_gender_fr(row.get("Gender"))
                    taille_m = row.get("Height (m)")
                    try:
                        taille_cm = round(float(taille_m) * 100.0, 2) if taille_m is not None else None
                    except Exception:
                        taille_cm = None

                    identity = build_random_identity(rng, conn, age=age, genre=gender)
                    payload = {
                        "organisation_id": rng.choice(org_ids),
                        "gym_external_id": f"GYM_MEMBER_{row_idx:06d}",
                        "sleep_external_id": str(row_idx) if row_idx <= sleep_count else None,
                        "nom_utilisateur": identity["nom_utilisateur"],
                        "prenom": identity["prenom"],
                        "nom": identity["nom"],
                        "email": identity["email"],
                        "date_naissance": identity["date_naissance"],
                        "genre": gender,
                        "taille_cm": taille_cm,
                        "role": "UTILISATEUR",
                        "statut": "ACTIF",
                        "mot_de_passe_hash": identity["mot_de_passe_hash"],
                    }
                    utilisateur_id = upsert_user(conn, payload)
                    writer.writerow({
                        "role": "UTILISATEUR",
                        "utilisateur_id": utilisateur_id,
                        "pseudonyme": payload["nom_utilisateur"],
                        "prenom": payload["prenom"],
                        "nom": payload["nom"],
                        "email": payload["email"],
                        "mot_de_passe_demo": identity["mot_de_passe_clair"],
                    })
                    stats.lignes_valides += 1

            set_lot_status(conn, lot_id, "NETTOYE", commentaire="Seed utilisateurs/organisations termine")

        with engine.begin() as conn:
            finish_execution(conn, execution_id, "SUCCES", stats, message="Seed utilisateurs/organisations termine")

        print(f"[USERS] OK - comptes crees/maj={stats.lignes_valides}")
    except Exception as exc:
        with engine.begin() as conn:
            finish_execution(conn, execution_id, "ECHEC", stats, message=str(exc)[:500])
        raise


if __name__ == "__main__":
    main()
