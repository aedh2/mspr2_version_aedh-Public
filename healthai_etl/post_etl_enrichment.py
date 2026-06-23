from __future__ import annotations

from datetime import date

from sqlalchemy import text

from etl_common import get_engine


def infer_objectif(latest_bmi: float | None, latest_sleep: float | None) -> str:
    if latest_sleep is not None and latest_sleep < 6.0:
        return "SOMMEIL"
    if latest_bmi is not None and latest_bmi >= 27.0:
        return "PERTE_POIDS"
    if latest_bmi is not None and latest_bmi < 20.0:
        return "GAIN_MUSCLE"
    return "MAINTIEN_FORME"


def build_commentaire(objectif: str, poids_kg: float | None, taille_cm: float | None, sommeil_h: float | None) -> str:
    taille_m = (taille_cm / 100.0) if taille_cm else None
    poids_ideal = round(22.0 * (taille_m ** 2), 1) if taille_m else None

    if objectif == "PERTE_POIDS":
        if poids_ideal is not None:
            return f"Atteindre progressivement un poids cible d'environ {poids_ideal} kg en restant regulier sur l'activite et l'alimentation."
        return "Reduire progressivement la masse grasse et retrouver un poids plus confortable."

    if objectif == "MAINTIEN_FORME":
        if poids_kg is not None:
            return f"Garder la meme forme generale et stabiliser le poids autour de {round(poids_kg, 1)} kg."
        return "Maintenir les habitudes actuelles et conserver un bon equilibre general."

    if objectif == "SOMMEIL":
        actuel = f"{round(sommeil_h, 1)} h" if sommeil_h is not None else "un sommeil insuffisant"
        return f"Eviter de rester a {actuel} de sommeil moyen et viser une cible reguliere entre 7.5 h et 8.0 h par nuit."

    if objectif == "GAIN_MUSCLE":
        if poids_kg is not None:
            gain = max(2.0, round(poids_kg * 0.06, 1))
            cible = round(poids_kg + gain, 1)
            return f"Pour un poids actuel de {round(poids_kg, 1)} kg, viser une augmentation musculaire progressive vers environ {cible} kg."
        return "Developper progressivement la masse musculaire avec des seances regulieres et une recuperation adaptee."

    return "Conserver un mode de vie sain et suivre regulierement les indicateurs de sante."


def main() -> None:
    engine = get_engine()
    with engine.begin() as conn:
        users = conn.execute(text("SELECT utilisateur_id FROM utilisateur WHERE role = 'UTILISATEUR' ORDER BY utilisateur_id")).mappings().all()
        for user in users:
            uid = int(user["utilisateur_id"])
            latest_bio = conn.execute(
                text(
                    """
                    SELECT poids_kg, taille_cm, imc
                      FROM mesure_biometrique
                     WHERE utilisateur_id = :uid
                     ORDER BY mesure_le DESC
                     LIMIT 1
                    """
                ),
                {"uid": uid},
            ).mappings().first()
            latest_sleep = conn.execute(
                text(
                    """
                    SELECT duree_sommeil_h
                      FROM mesure_sommeil_sante
                     WHERE utilisateur_id = :uid
                     ORDER BY mesure_le DESC
                     LIMIT 1
                    """
                ),
                {"uid": uid},
            ).mappings().first()

            latest_bmi = float(latest_bio["imc"]) if latest_bio and latest_bio["imc"] is not None else None
            latest_sleep_h = float(latest_sleep["duree_sommeil_h"]) if latest_sleep and latest_sleep["duree_sommeil_h"] is not None else None
            poids = float(latest_bio["poids_kg"]) if latest_bio and latest_bio["poids_kg"] is not None else None
            taille = float(latest_bio["taille_cm"]) if latest_bio and latest_bio["taille_cm"] is not None else None

            objectif = infer_objectif(latest_bmi, latest_sleep_h)
            commentaire = build_commentaire(objectif, poids, taille, latest_sleep_h)

            active = conn.execute(
                text("SELECT objectif_id FROM objectif_utilisateur WHERE utilisateur_id = :uid AND actif_unique = 1 AND date_fin IS NULL LIMIT 1"),
                {"uid": uid},
            ).mappings().first()

            if active:
                conn.execute(
                    text(
                        """
                        UPDATE objectif_utilisateur
                           SET type_objectif = :objectif,
                               commentaire = :commentaire
                         WHERE objectif_id = :objectif_id
                        """
                    ),
                    {"objectif_id": int(active["objectif_id"]), "objectif": objectif, "commentaire": commentaire},
                )
            else:
                conn.execute(
                    text(
                        """
                        INSERT INTO objectif_utilisateur (
                          utilisateur_id, type_objectif, date_debut, date_fin, actif_unique, commentaire, cree_le
                        ) VALUES (
                          :uid, :objectif, :date_debut, NULL, 1, :commentaire, NOW()
                        )
                        """
                    ),
                    {"uid": uid, "objectif": objectif, "date_debut": date.today(), "commentaire": commentaire},
                )
    print("Objectifs personnalises calcules pour les utilisateurs.")


if __name__ == "__main__":
    main()
