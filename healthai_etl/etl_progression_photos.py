from __future__ import annotations

import os
from datetime import date
from pathlib import Path

from sqlalchemy import text

from etl_common import ensure_demo_user, get_engine, get_organisation_id


def pick_two_users(conn, organisation_id: int) -> list[int]:
    rows = conn.execute(text("SELECT utilisateur_id FROM utilisateur WHERE role = 'UTILISATEUR' ORDER BY utilisateur_id LIMIT 2")).mappings().all()
    ids = [int(r["utilisateur_id"]) for r in rows]
    while len(ids) < 2:
        ids.append(ensure_demo_user(conn, f"@photo.demo.{len(ids)+1}", organisation_id))
    return ids[:2]


def latest_objectif(conn, utilisateur_id: int) -> int | None:
    row = conn.execute(text("SELECT objectif_id FROM objectif_utilisateur WHERE utilisateur_id = :uid ORDER BY cree_le DESC LIMIT 1"), {"uid": utilisateur_id}).mappings().first()
    return int(row["objectif_id"]) if row else None


def insert_if_missing(conn, utilisateur_id: int, objectif_id: int | None, type_photo: str, image_path: str, prise_le: date) -> None:
    exists = conn.execute(text("SELECT photo_id FROM progression_photo WHERE utilisateur_id = :uid AND image_path = :path LIMIT 1"), {"uid": utilisateur_id, "path": image_path}).mappings().first()
    if exists:
        return
    conn.execute(
        text(
            """
            INSERT INTO progression_photo (
              utilisateur_id, objectif_id, type_photo, image_path, prise_le, cree_le
            ) VALUES (
              :uid, :objectif_id, :type_photo, :image_path, :prise_le, NOW()
            )
            """
        ),
        {
            "uid": utilisateur_id,
            "objectif_id": objectif_id,
            "type_photo": type_photo,
            "image_path": image_path,
            "prise_le": prise_le,
        },
    )


def main() -> None:
    photos_dir = Path(os.getenv("PROGRESSION_PHOTOS_DIR", "before after"))
    if not photos_dir.exists():
        print(f"Dossier introuvable: {photos_dir}")
        return

    engine = get_engine()
    with engine.begin() as conn:
        organisation_id = get_organisation_id(conn, "HealthAI Public")
        user_a, user_b = pick_two_users(conn, organisation_id)
        objectif_a = latest_objectif(conn, user_a)
        objectif_b = latest_objectif(conn, user_b)

        mapping = {
            "before1": (user_a, objectif_a, "BEFORE"),
            "after1": (user_a, objectif_a, "AFTER"),
            "before2": (user_b, objectif_b, "BEFORE"),
            "after2": (user_b, objectif_b, "AFTER"),
        }

        for file in sorted(photos_dir.iterdir()):
            if file.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
                continue
            lower = file.stem.lower()
            if lower not in mapping:
                continue
            uid, objectif_id, type_photo = mapping[lower]
            insert_if_missing(conn, uid, objectif_id, type_photo, str(file).replace("\\", "/"), date.today())

    print("Photos de progression importees pour 2 utilisateurs distincts.")


if __name__ == "__main__":
    main()
