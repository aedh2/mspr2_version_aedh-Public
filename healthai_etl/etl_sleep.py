from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from etl_common import (
    ExecutionStats,
    as_text,
    birthdate_from_age,
    build_anomaly,
    build_demo_datetime,
    build_reject,
    create_execution,
    create_lot,
    ensure_user_by_source_identity,
    find_user_by_source_identity,
    finish_execution,
    get_engine,
    get_organisation_id,
    get_source_id,
    insert_anomalies,
    insert_raw_records,
    insert_rejects,
    insert_stg_records,
    normalize_gender_fr,
    normalize_sleep_disorder,
    parse_blood_pressure,
    parse_env_date,
    safe_json_dumps,
    seed_quality_rules,
    set_lot_status,
    to_float,
    to_int,
)

SLEEP_REQUIRED = [
    "Person ID", "Gender", "Age", "Occupation", "Sleep Duration", "Quality of Sleep",
    "Physical Activity Level", "Stress Level", "BMI Category", "Blood Pressure",
    "Heart Rate", "Daily Steps", "Sleep Disorder",
]


def main() -> None:
    csv_path = os.getenv("SLEEP_CSV", str(Path(__file__).resolve().parent.parent / "Sleep_health_and_lifestyle_dataset.csv"))
    measure_date = parse_env_date("SLEEP_MEASURE_DATE")

    engine = get_engine()
    stats = ExecutionStats()
    anomalies: list[dict] = []
    rejects: list[dict] = []

    with engine.begin() as conn:
        source_id = get_source_id(conn, "Sleep Health and Lifestyle Dataset")
        organisation_id = get_organisation_id(conn, "HealthAI Public")
        execution_id = create_execution(conn, source_id)
        rule_ids = seed_quality_rules(conn)

    try:
        df = pd.read_csv(csv_path)
        stats.lignes_lues = len(df)
        missing = [c for c in SLEEP_REQUIRED if c not in df.columns]
        if missing:
            raise RuntimeError(f"Colonnes manquantes: {missing}")

        df = df.reset_index(drop=True)
        df["__line_number"] = df.index + 2
        raw_rows = df[SLEEP_REQUIRED + ["__line_number"]].to_dict(orient="records")

        with engine.begin() as conn:
            lot_id = create_lot(conn, execution_id, source_id, f"sleep_{pd.Timestamp.now():%Y%m%d_%H%M%S}")
            set_lot_status(conn, lot_id, "VALIDE")
            insert_raw_records(conn, lot_id, "sleep", raw_rows, ref_key="Person ID")

            stg_records: list[dict] = []
            seen_persons: set[str] = set()

            for row_idx, row in enumerate(raw_rows, start=1):
                ref_line = str(row["__line_number"])
                person_id = as_text(row.get("Person ID"))
                if person_id in seen_persons:
                    stats.nb_doublons_supprimes += 1
                    anomalies.append(build_anomaly(execution_id, lot_id, None, "AVERT", "sleep", ref_line, "Person ID", "SLEEP_DUPLICATE_PERSON", f"Person ID repete dans le lot: {person_id}", person_id))
                    continue
                if person_id:
                    seen_persons.add(person_id)

                age = to_int(row.get("Age"))
                sleep_h = to_float(row.get("Sleep Duration"))
                quality = to_float(row.get("Quality of Sleep"))
                activity = to_float(row.get("Physical Activity Level"))
                stress = to_float(row.get("Stress Level"))
                heart = to_int(row.get("Heart Rate"))
                steps = to_int(row.get("Daily Steps"))
                sys_bp, dia_bp = parse_blood_pressure(row.get("Blood Pressure"))
                normalized_disorder = normalize_sleep_disorder(row.get("Sleep Disorder"))
                genre_fr = normalize_gender_fr(row.get("Gender"))

                normalized = {
                    "person_id_source": person_id,
                    "genre_source": genre_fr,
                    "age_source": age,
                    "profession": as_text(row.get("Occupation")),
                    "duree_sommeil_h": sleep_h,
                    "qualite_sommeil_score": quality,
                    "activite_physique_min_jour": activity,
                    "stress_score": stress,
                    "categorie_imc_source": as_text(row.get("BMI Category")),
                    "tension_arterielle_brut": as_text(row.get("Blood Pressure")),
                    "tension_systolique": sys_bp,
                    "tension_diastolique": dia_bp,
                    "frequence_cardiaque_bpm": heart,
                    "pas_jour": steps,
                    "trouble_sommeil_brut": as_text(row.get("Sleep Disorder")),
                    "trouble_sommeil_normalise": normalized_disorder,
                }

                parseable = True
                status = "VALIDE"
                reject_code = None

                if not person_id:
                    parseable = False
                    status = "REJETE"
                    reject_code = "SLEEP_REQUIRED_ID"
                    anomalies.append(build_anomaly(execution_id, lot_id, None, "ERREUR", "sleep", ref_line, "Person ID", "SLEEP_REQUIRED_ID", "Person ID manquant"))

                if sleep_h is None or not (0 < sleep_h <= 24):
                    parseable = False
                    status = "REJETE"
                    reject_code = "SLEEP_HOURS_RANGE"
                    anomalies.append(build_anomaly(execution_id, lot_id, rule_ids.get("SLEEP_HOURS_RANGE"), "ERREUR", "sleep", ref_line, "Sleep Duration", "SLEEP_HOURS_RANGE", f"Duree de sommeil invalide: {row.get('Sleep Duration')}", row.get("Sleep Duration")))

                if sys_bp is None or dia_bp is None:
                    parseable = False
                    status = "REJETE"
                    reject_code = "SLEEP_BP_FORMAT"
                    anomalies.append(build_anomaly(execution_id, lot_id, rule_ids.get("SLEEP_BP_FORMAT"), "ERREUR", "sleep", ref_line, "Blood Pressure", "SLEEP_BP_FORMAT", f"Format tension invalide: {row.get('Blood Pressure')}", row.get("Blood Pressure")))
                elif sys_bp <= dia_bp:
                    parseable = False
                    status = "REJETE"
                    reject_code = "SLEEP_BP_ORDER"
                    anomalies.append(build_anomaly(execution_id, lot_id, rule_ids.get("SLEEP_BP_ORDER"), "ERREUR", "sleep", ref_line, "Blood Pressure", "SLEEP_BP_ORDER", f"Tension incoherente SYS={sys_bp} DIA={dia_bp}", row.get("Blood Pressure")))

                if normalized_disorder == "Autre":
                    anomalies.append(build_anomaly(execution_id, lot_id, rule_ids.get("SLEEP_DISORDER_REF"), "AVERT", "sleep", ref_line, "Sleep Disorder", "SLEEP_DISORDER_REF", f"Trouble du sommeil inhabituel: {row.get('Sleep Disorder')}", row.get("Sleep Disorder")))
                    if status == "VALIDE":
                        status = "AVERTISSEMENT"

                ext_id = person_id or f"sleep_line_{ref_line}"
                stg_records.append({
                    "lot_id": lot_id,
                    "entite": "sleep",
                    "ref_externe": ext_id,
                    "source_payload_json": safe_json_dumps(row),
                    "payload_normalise_json": safe_json_dumps(normalized),
                    "est_parseable": 1 if parseable else 0,
                    "statut_validation": status,
                    "code_rejet_potentiel": reject_code,
                })

                if status == "REJETE":
                    stats.lignes_invalides += 1
                    stats.nb_rejets += 1
                    rejects.append(build_reject(execution_id, lot_id, "sleep", ext_id, row, reject_code or "SLEEP_REJECT", "Ligne sommeil rejetee pendant validation"))
                    continue

                utilisateur_id = find_user_by_source_identity(conn, source_id, ext_id)
                if utilisateur_id is None:
                    utilisateur_id = ensure_user_by_source_identity(
                        conn,
                        source_id,
                        ext_id,
                        f"@sleep.member.{int(ext_id):06d}" if str(ext_id).isdigit() else f"@sleep.{ref_line}",
                        organisation_id=organisation_id,
                        defaults={
                            "genre": genre_fr,
                            "date_naissance": birthdate_from_age(age),
                            "role": "UTILISATEUR",
                            "statut": "ACTIF",
                        },
                    )

                conn.execute(
                    text(
                        """
                        UPDATE utilisateur
                           SET genre = COALESCE(NULLIF(genre, 'Inconnu'), :genre, genre),
                               date_naissance = COALESCE(date_naissance, :date_naissance),
                               modifie_le = NOW()
                         WHERE utilisateur_id = :utilisateur_id
                        """
                    ),
                    {"utilisateur_id": utilisateur_id, "genre": genre_fr, "date_naissance": birthdate_from_age(age)},
                )

                measure_dt = build_demo_datetime(measure_date, 7, row_idx)
                existing = conn.execute(text("SELECT mesure_sommeil_id FROM mesure_sommeil_sante WHERE utilisateur_id = :uid AND mesure_le = :mesure_le LIMIT 1"), {"uid": utilisateur_id, "mesure_le": measure_dt}).mappings().first()
                if not existing:
                    conn.execute(
                        text(
                            """
                            INSERT INTO mesure_sommeil_sante (
                              utilisateur_id, source_id, lot_id, mesure_le, person_id_source,
                              genre_source, age_source, profession, duree_sommeil_h,
                              qualite_sommeil_score, activite_physique_min_jour, stress_score,
                              categorie_imc_source, tension_arterielle_brut, tension_systolique,
                              tension_diastolique, frequence_cardiaque_bpm, pas_jour,
                              trouble_sommeil_brut, trouble_sommeil_normalise, cree_le
                            ) VALUES (
                              :utilisateur_id, :source_id, :lot_id, :mesure_le, :person_id_source,
                              :genre_source, :age_source, :profession, :duree_sommeil_h,
                              :qualite_sommeil_score, :activite_physique_min_jour, :stress_score,
                              :categorie_imc_source, :tension_arterielle_brut, :tension_systolique,
                              :tension_diastolique, :frequence_cardiaque_bpm, :pas_jour,
                              :trouble_sommeil_brut, :trouble_sommeil_normalise, NOW()
                            )
                            """
                        ),
                        {
                            "utilisateur_id": utilisateur_id,
                            "source_id": source_id,
                            "lot_id": lot_id,
                            "mesure_le": measure_dt,
                            "person_id_source": person_id,
                            "genre_source": genre_fr,
                            "age_source": age,
                            "profession": normalized["profession"],
                            "duree_sommeil_h": sleep_h,
                            "qualite_sommeil_score": quality,
                            "activite_physique_min_jour": activity,
                            "stress_score": stress,
                            "categorie_imc_source": normalized["categorie_imc_source"],
                            "tension_arterielle_brut": normalized["tension_arterielle_brut"],
                            "tension_systolique": sys_bp,
                            "tension_diastolique": dia_bp,
                            "frequence_cardiaque_bpm": heart,
                            "pas_jour": steps,
                            "trouble_sommeil_brut": normalized["trouble_sommeil_brut"],
                            "trouble_sommeil_normalise": normalized_disorder,
                        },
                    )
                stats.lignes_valides += 1

            insert_stg_records(conn, stg_records)
            insert_anomalies(conn, anomalies)
            insert_rejects(conn, rejects)
            set_lot_status(conn, lot_id, "NETTOYE", commentaire="ETL sleep termine")

        with engine.begin() as conn:
            finish_execution(conn, execution_id, "SUCCES", stats, message="ETL sleep termine")

        print(f"[SLEEP] OK - lues={stats.lignes_lues} valides={stats.lignes_valides} invalides={stats.lignes_invalides} doublons={stats.nb_doublons_supprimes}")
    except Exception as exc:
        with engine.begin() as conn:
            finish_execution(conn, execution_id, "ECHEC", stats, message=str(exc)[:500])
        raise


if __name__ == "__main__":
    main()
