from __future__ import annotations

import os
import random
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from etl_common import (
    ExecutionStats,
    as_text,
    build_anomaly,
    build_demo_datetime,
    build_reject,
    create_execution,
    create_lot,
    ensure_aliment,
    ensure_demo_user,
    ensure_plat,
    finish_execution,
    get_engine,
    get_organisation_id,
    get_source_id,
    insert_anomalies,
    insert_raw_records,
    insert_rejects,
    insert_stg_records,
    is_blank,
    normalize_meal_type,
    parse_env_date,
    safe_json_dumps,
    seed_quality_rules,
    set_lot_status,
    to_float,
)

FOOD_EXPECTED_COLS = [
    "Food_Item", "Category", "Calories (kcal)", "Protein (g)", "Carbohydrates (g)",
    "Fat (g)", "Fiber (g)", "Sugars (g)", "Sodium (mg)", "Cholesterol (mg)",
    "Meal_Type", "Water_Intake (ml)",
]


def read_food_csv_robust(path: str) -> pd.DataFrame:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.read().splitlines()
    header = lines[0].split(",")
    if len(header) != 12:
        header = FOOD_EXPECTED_COLS
    rows = []
    for line_number, line in enumerate(lines[1:], start=2):
        parts = line.split(",")
        if len(parts) < 12:
            continue
        if len(parts) > 12:
            food_item = ",".join(parts[:-11]).strip()
            rest = parts[-11:]
            parts = [food_item] + rest
        row = dict(zip(header, parts[:12]))
        row["__line_number"] = line_number
        rows.append(row)
    return pd.DataFrame(rows)


def get_food_target_users(conn, organisation_id: int) -> list[int]:
    rows = conn.execute(text("SELECT utilisateur_id FROM utilisateur WHERE role = 'UTILISATEUR' ORDER BY utilisateur_id")).mappings().all()
    ids = [int(r["utilisateur_id"]) for r in rows]
    if ids:
        return ids
    return [ensure_demo_user(conn, "@demo.food.user", organisation_id)]


def get_admin_user_for_lot(conn, organisation_id: int) -> int:
    row = conn.execute(text("SELECT utilisateur_id FROM utilisateur WHERE role IN ('ADMIN','SUPER_ADMIN') ORDER BY role DESC, utilisateur_id LIMIT 1")).mappings().first()
    if row:
        return int(row["utilisateur_id"])
    return ensure_demo_user(conn, "@admin.food.seed", organisation_id, role="ADMIN")


def meal_hour(meal_type: str) -> int:
    if meal_type == "PetitDejeuner":
        return 8
    if meal_type == "Dejeuner":
        return 12
    if meal_type == "Diner":
        return 19
    return 16


def main() -> None:
    csv_path = os.getenv("FOOD_CSV", str(Path(__file__).resolve().parent.parent / "daily_food_nutrition_dataset.csv"))
    import_date = parse_env_date("FOOD_IMPORT_DATE")
    rng = random.Random(20260430)

    engine = get_engine()
    stats = ExecutionStats()
    anomalies: list[dict] = []
    rejects: list[dict] = []

    with engine.begin() as conn:
        source_id = get_source_id(conn, "Daily Food Nutrition Dataset")
        organisation_id = get_organisation_id(conn, "HealthAI Public")
        execution_id = create_execution(conn, source_id)
        rule_ids = seed_quality_rules(conn)

    try:
        df = read_food_csv_robust(csv_path)
        stats.lignes_lues = len(df)
        missing = [c for c in FOOD_EXPECTED_COLS if c not in df.columns]
        if missing:
            raise RuntimeError(f"Colonnes manquantes: {missing}")
        raw_rows = df[FOOD_EXPECTED_COLS + ["__line_number"]].to_dict(orient="records")

        with engine.begin() as conn:
            admin_user_id = get_admin_user_for_lot(conn, organisation_id)
            target_user_ids = get_food_target_users(conn, organisation_id)
            lot_id = create_lot(conn, execution_id, source_id, f"food_{pd.Timestamp.now():%Y%m%d_%H%M%S}", cree_par=admin_user_id)
            set_lot_status(conn, lot_id, "VALIDE")
            insert_raw_records(conn, lot_id, "food", raw_rows)

            stg_records: list[dict] = []
            processed_catalogue: set[str] = set()
            validated_entries: list[dict] = []

            for row_idx, row in enumerate(raw_rows, start=1):
                ref_line = str(row.get("__line_number", row_idx))
                food_item = as_text(row.get("Food_Item"))
                category = as_text(row.get("Category"))
                meal_type = normalize_meal_type(row.get("Meal_Type"))
                normalized = {
                    "food_item": food_item,
                    "category": category,
                    "calories_kcal": to_float(row.get("Calories (kcal)")),
                    "proteines_g": to_float(row.get("Protein (g)")),
                    "glucides_g": to_float(row.get("Carbohydrates (g)")),
                    "lipides_g": to_float(row.get("Fat (g)")),
                    "fibres_g": to_float(row.get("Fiber (g)")),
                    "sucres_g": to_float(row.get("Sugars (g)")),
                    "sodium_mg": to_float(row.get("Sodium (mg)")),
                    "cholesterol_mg": to_float(row.get("Cholesterol (mg)")),
                    "type_repas": meal_type,
                    "eau_ml": to_float(row.get("Water_Intake (ml)")),
                }

                parseable = True
                status = "VALIDE"
                reject_code = None
                corrected = 0

                if is_blank(food_item):
                    parseable = False
                    status = "REJETE"
                    reject_code = "FOOD_REQUIRED_ITEM"
                    anomalies.append(build_anomaly(execution_id, lot_id, rule_ids.get("FOOD_REQUIRED_ITEM"), "ERREUR", "food", ref_line, "Food_Item", "FOOD_REQUIRED_ITEM", "Nom d'aliment manquant"))

                calories = normalized["calories_kcal"]
                if calories is not None and not (0 <= calories <= 3000):
                    if status != "REJETE":
                        status = "AVERTISSEMENT"
                    anomalies.append(build_anomaly(execution_id, lot_id, rule_ids.get("FOOD_CAL_RANGE"), "AVERT", "food", ref_line, "Calories (kcal)", "FOOD_CAL_RANGE", f"Calories hors plage plausible: {calories}", calories))

                if meal_type == "Autre":
                    anomalies.append(build_anomaly(execution_id, lot_id, rule_ids.get("FOOD_MEAL_REF"), "AVERT", "food", ref_line, "Meal_Type", "FOOD_MEAL_REF", f"Type de repas non reference: {row.get('Meal_Type')}", row.get("Meal_Type")))
                    if status == "VALIDE":
                        status = "AVERTISSEMENT"

                if normalized["eau_ml"] is None:
                    normalized["eau_ml"] = 0.0
                    corrected += 1

                ref_externe = f"FOOD_LINE_{row_idx:06d}"
                stg_records.append({
                    "lot_id": lot_id,
                    "entite": "food",
                    "ref_externe": ref_externe,
                    "source_payload_json": safe_json_dumps(row),
                    "payload_normalise_json": safe_json_dumps(normalized),
                    "est_parseable": 1 if parseable else 0,
                    "statut_validation": status,
                    "code_rejet_potentiel": reject_code,
                })

                if status == "REJETE":
                    stats.lignes_invalides += 1
                    stats.nb_rejets += 1
                    rejects.append(build_reject(execution_id, lot_id, "food", ref_externe, row, reject_code or "FOOD_REJECT", "Ligne alimentaire rejetee pendant validation"))
                    continue

                stats.nb_valeurs_corrigees += corrected
                stats.lignes_valides += 1

                catalogue_key = (food_item or "").strip().lower()
                if catalogue_key in processed_catalogue:
                    stats.nb_doublons_supprimes += 1
                else:
                    processed_catalogue.add(catalogue_key)
                    ensure_aliment(conn, source_id, food_item, {
                        "categorie": category,
                        "calories_kcal": normalized["calories_kcal"],
                        "proteines_g": normalized["proteines_g"],
                        "glucides_g": normalized["glucides_g"],
                        "lipides_g": normalized["lipides_g"],
                        "fibres_g": normalized["fibres_g"],
                        "sucres_g": normalized["sucres_g"],
                        "sodium_mg": normalized["sodium_mg"],
                        "cholesterol_mg": normalized["cholesterol_mg"],
                    })

                aliment_row = conn.execute(text("SELECT aliment_id, nom FROM aliment WHERE nom = :nom LIMIT 1"), {"nom": food_item}).mappings().first()
                aliment_id = int(aliment_row["aliment_id"]) if aliment_row else None
                aliment_nom = str(aliment_row["nom"]) if aliment_row else food_item
                validated_entries.append({
                    "food_item": aliment_nom,
                    "aliment_id": aliment_id,
                    "type_repas": meal_type,
                    "calories_kcal": float(normalized["calories_kcal"] or 0.0),
                    "eau_ml": float(normalized["eau_ml"] or 0.0),
                })

            insert_stg_records(conn, stg_records)
            insert_anomalies(conn, anomalies)
            insert_rejects(conn, rejects)

            current_plate: list[dict] = []
            current_meal_type = None
            plate_number = 0
            user_index = 0

            def flush_plate() -> None:
                nonlocal current_plate, current_meal_type, plate_number, user_index
                if not current_plate:
                    return
                plate_number += 1
                utilisateur_id = target_user_ids[user_index % len(target_user_ids)]
                user_index += 1
                consomme_le = build_demo_datetime(import_date, meal_hour(current_meal_type), plate_number, slot_minutes=41)
                lignes = []
                for item in current_plate:
                    quantite = rng.randint(1, 4)
                    calories_ligne = round(float(item["calories_kcal"]) * quantite, 2)
                    lignes.append({
                        "aliment_id": item["aliment_id"],
                        "aliment_nom_libre": item["food_item"],
                        "quantite": quantite,
                        "unite_quantite": "portion",
                        "calories_kcal": calories_ligne,
                        "eau_ml": float(item["eau_ml"]),
                    })
                total_calories = round(sum(l["calories_kcal"] for l in lignes), 2)
                nom_plat = f"Plat {current_meal_type} #{plate_number}"
                plat_id = ensure_plat(conn, utilisateur_id, source_id, lot_id, consomme_le, current_meal_type, nom_plat, total_calories)
                for ligne in lignes:
                    conn.execute(
                        text(
                            """
                            INSERT INTO journal_alimentaire (
                              utilisateur_id, plat_id, aliment_id, source_id, lot_id, consomme_le,
                              type_repas, aliment_nom_libre, quantite, unite_quantite,
                              calories_kcal, eau_ml, cree_le
                            ) VALUES (
                              :utilisateur_id, :plat_id, :aliment_id, :source_id, :lot_id, :consomme_le,
                              :type_repas, :aliment_nom_libre, :quantite, :unite_quantite,
                              :calories_kcal, :eau_ml, NOW()
                            )
                            """
                        ),
                        {
                            "utilisateur_id": utilisateur_id,
                            "plat_id": plat_id,
                            "aliment_id": ligne["aliment_id"],
                            "source_id": source_id,
                            "lot_id": lot_id,
                            "consomme_le": consomme_le,
                            "type_repas": current_meal_type,
                            "aliment_nom_libre": ligne["aliment_nom_libre"],
                            "quantite": ligne["quantite"],
                            "unite_quantite": ligne["unite_quantite"],
                            "calories_kcal": ligne["calories_kcal"],
                            "eau_ml": ligne["eau_ml"],
                        },
                    )
                conn.execute(
                    text(
                        """
                        UPDATE plat
                           SET calories_totales_kcal = (
                               SELECT COALESCE(ROUND(SUM(j.calories_kcal), 2), 0)
                                 FROM journal_alimentaire j
                                WHERE j.plat_id = :plat_id
                           )
                         WHERE plat_id = :plat_id
                        """
                    ),
                    {"plat_id": plat_id},
                )
                current_plate = []
                current_meal_type = None

            for item in validated_entries:
                if not current_plate:
                    current_plate.append(item)
                    current_meal_type = item["type_repas"]
                    continue
                if current_meal_type == item["type_repas"] and len(current_plate) < 3:
                    current_plate.append(item)
                else:
                    flush_plate()
                    current_plate.append(item)
                    current_meal_type = item["type_repas"]
            flush_plate()

            set_lot_status(conn, lot_id, "NETTOYE", valide_par=admin_user_id, commentaire="ETL food termine")

        with engine.begin() as conn:
            finish_execution(conn, execution_id, "SUCCES", stats, message="ETL food termine")

        print(f"[FOOD] OK - lues={stats.lignes_lues} valides={stats.lignes_valides} invalides={stats.lignes_invalides} doublons={stats.nb_doublons_supprimes}")
    except Exception as exc:
        with engine.begin() as conn:
            finish_execution(conn, execution_id, "ECHEC", stats, message=str(exc)[:500])
        raise


if __name__ == "__main__":
    main()
