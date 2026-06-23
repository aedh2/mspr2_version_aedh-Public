from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from collections.abc import Generator

from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.core.rate_limit import limiter
from app.core.security import hash_password_pbkdf2_sha256
from app.db.base import Base
from app.db.models import (
    Aliment,
    CoachPostureSession,
    Exercice,
    MesureBiometrique,
    MesureSommeilSante,
    ObjectifUtilisateur,
    Organisation,
    Plat,
    Utilisateur,
)
from app.db.session import get_db
from app.main import app

TINY_PNG_DATA_URL = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8"
    "/w8AAgMBgL+5lGQAAAAASUVORK5CYII="
)


@pytest.fixture(autouse=True)
def reset_ai_settings(monkeypatch: pytest.MonkeyPatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "ai_enable_external_calls", False, raising=False)
    monkeypatch.setattr(settings, "meal_ai_force_mock", False, raising=False)
    monkeypatch.setattr(settings, "hf_token", None, raising=False)
    monkeypatch.setattr(settings, "huggingface_api_token", None, raising=False)
    monkeypatch.setattr(settings, "deepseek_api_key", None, raising=False)
    if hasattr(limiter, "reset"):
        limiter.reset()


@pytest.fixture()
def testing_session_factory() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    with TestingSession() as session:
        org = Organisation(nom="HealthAI Public", adresse="Paris")
        session.add(org)
        session.flush()
        session.add_all(
            [
                Utilisateur(
                    organisation_id=org.organisation_id,
                    nom_utilisateur="alice",
                    email="alice@example.test",
                    role="UTILISATEUR",
                    statut="ACTIF",
                    mot_de_passe_hash=hash_password_pbkdf2_sha256("secret"),
                ),
                Utilisateur(
                    organisation_id=org.organisation_id,
                    nom_utilisateur="admin",
                    email="admin@example.test",
                    role="ADMIN",
                    statut="ACTIF",
                    mot_de_passe_hash=hash_password_pbkdf2_sha256("admin-secret"),
                ),
                Utilisateur(
                    organisation_id=org.organisation_id,
                    nom_utilisateur="superadmin",
                    email="superadmin@example.test",
                    role="SUPER_ADMIN",
                    statut="ACTIF",
                    mot_de_passe_hash=hash_password_pbkdf2_sha256("superadmin-secret"),
                ),
            ]
        )
        session.commit()
    return TestingSession


@pytest.fixture()
def db_session(testing_session_factory: sessionmaker[Session]) -> Generator[Session, None, None]:
    with testing_session_factory() as session:
        yield session


@pytest.fixture()
def client(testing_session_factory: sessionmaker[Session]) -> TestClient:
    def override_get_db():
        with testing_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def login(client: TestClient, identifiant: str, mot_de_passe: str) -> dict:
    response = client.post(
        "/api/auth/login",
        json={"identifiant": identifiant, "mot_de_passe": mot_de_passe},
    )
    assert response.status_code == 200
    return response.json()


def auth_headers(client: TestClient, identifiant: str = "admin", password: str = "admin-secret") -> dict[str, str]:
    token = login(client, identifiant, password)["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def complete_register_payload(
    *,
    username: str = "new-user",
    email: str = "new-user@example.test",
    password: str = "Secret123",
    objectif: str = "PERTE_POIDS",
) -> dict:
    return {
        "nom_utilisateur": username,
        "email": email,
        "mot_de_passe": password,
        "confirmation": password,
        "prenom": "Nora",
        "nom": "Data",
        "taille_cm": 170,
        "poids_actuel_kg": 72,
        "poids_cible_kg": 66,
        "objectif_principal": objectif,
        "date_cible": "2030-12-31",
        "niveau_activite": "modere",
        "allergies": ["arachide"],
        "regime_alimentaire": "vegetarien",
        "contraintes_sante": ["douleur genou"],
    }


def test_login_me_and_refresh_use_french_contract(client: TestClient):
    login_payload = login(client, "alice", "secret")

    assert login_payload["data"]["token_type"] == "bearer"
    assert "refresh_token" in client.cookies

    headers = {"Authorization": f"Bearer {login_payload['data']['access_token']}"}
    me = client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["data"]["nom_utilisateur"] == "alice"

    refreshed = client.post("/api/auth/refresh")
    assert refreshed.status_code == 200
    assert refreshed.json()["data"]["token_type"] == "bearer"


def test_health_and_openapi(client: TestClient):
    assert client.get("/health").status_code == 200
    response = client.get("/api/openapi.json")
    assert response.status_code == 200
    assert "paths" in response.json()


def test_register_availability_does_not_create_user(client: TestClient, db_session: Session):
    before = db_session.scalar(
        select(func.count(Utilisateur.utilisateur_id)).where(Utilisateur.nom_utilisateur == "draft-only")
    )

    response = client.get(
        "/api/auth/register-availability",
        params={"nom_utilisateur": "draft-only", "email": "draft-only@example.test"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["nom_utilisateur_disponible"] is True
    assert data["email_disponible"] is True
    after = db_session.scalar(
        select(func.count(Utilisateur.utilisateur_id)).where(Utilisateur.nom_utilisateur == "draft-only")
    )
    assert before == after == 0


def test_register_availability_identifies_incomplete_user2_without_deleting(client: TestClient, db_session: Session):
    org = db_session.query(Organisation).first()
    db_session.add(
        Utilisateur(
            organisation_id=org.organisation_id if org else None,
            nom_utilisateur="user2",
            email="user2@example.test",
            role="UTILISATEUR",
            statut="ACTIF",
            onboarding_complete=False,
            mot_de_passe_hash=hash_password_pbkdf2_sha256("Secret123"),
        )
    )
    db_session.commit()

    response = client.get(
        "/api/auth/register-availability",
        params={"nom_utilisateur": "user2", "email": "user2@example.test"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["nom_utilisateur_disponible"] is False
    assert data["email_disponible"] is False
    assert data["nom_utilisateur_compte_incomplet"] is True
    assert data["email_compte_incomplet"] is True
    assert data["nom_utilisateur_suppression_sure_possible"] is True
    assert db_session.scalar(select(func.count(Utilisateur.utilisateur_id)).where(Utilisateur.nom_utilisateur == "user2")) == 1


def test_register_complete_reports_incomplete_account_without_creating_duplicate(client: TestClient, db_session: Session):
    org = db_session.query(Organisation).first()
    db_session.add(
        Utilisateur(
            organisation_id=org.organisation_id if org else None,
            nom_utilisateur="user2",
            email="user2@example.test",
            role="UTILISATEUR",
            statut="ACTIF",
            onboarding_complete=False,
            mot_de_passe_hash=hash_password_pbkdf2_sha256("Secret123"),
        )
    )
    db_session.commit()

    response = client.post(
        "/api/auth/register-complete",
        json=complete_register_payload(username="user2", email="fresh-user2@example.test"),
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "username_incomplete"
    assert db_session.scalar(select(func.count(Utilisateur.utilisateur_id)).where(Utilisateur.nom_utilisateur == "user2")) == 1


def test_register_complete_creates_user_profile_records_and_token(client: TestClient, db_session: Session):
    response = client.post("/api/auth/register-complete", json=complete_register_payload())

    assert response.status_code == 201
    body = response.json()["data"]
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["onboarding_complete"] is True

    user = db_session.query(Utilisateur).filter_by(nom_utilisateur="new-user").one()
    assert user.prenom == "Nora"
    assert user.allergies_json == '["arachide"]'
    assert user.contraintes_sante_json == '["douleur genou"]'
    assert user.niveau_activite == "modere"
    assert user.onboarding_complete is True

    bio = db_session.query(MesureBiometrique).filter_by(utilisateur_id=user.utilisateur_id).one()
    assert bio.poids_kg == 72
    assert bio.taille_cm == 170
    assert bio.imc == pytest.approx(24.91, abs=0.01)

    objective = db_session.query(ObjectifUtilisateur).filter_by(utilisateur_id=user.utilisateur_id).one()
    assert objective.type_objectif == "PERTE_POIDS"
    assert objective.poids_cible_kg == 66
    assert objective.actif_unique is True

    sleep_count = db_session.scalar(
        select(func.count(MesureSommeilSante.mesure_sommeil_id)).where(
            MesureSommeilSante.utilisateur_id == user.utilisateur_id
        )
    )
    assert sleep_count == 0


def test_register_complete_accepts_french_decimal_and_labels(client: TestClient, db_session: Session):
    payload = complete_register_payload(
        username="prise-masse-fr",
        email="prise-masse-fr@example.test",
        objectif="Prise de masse",
    )
    payload.update(
        {
            "taille_cm": "155",
            "poids_actuel_kg": "55",
            "poids_cible_kg": "62,9",
            "date_cible": "2030-06-26",
            "niveau_activite": "Léger",
            "allergies": ["lactose"],
            "regime_alimentaire": "Végétarien",
            "contraintes_sante": ["cardiaque"],
        }
    )

    response = client.post("/api/auth/register-complete", json=payload)

    assert response.status_code == 201
    body = response.json()["data"]
    assert body["access_token"]
    user = db_session.query(Utilisateur).filter_by(nom_utilisateur="prise-masse-fr").one()
    assert user.genre == "Inconnu"
    assert user.niveau_activite == "leger"
    assert user.allergies_json == '["lactose"]'
    assert user.regime_alimentaire == "Végétarien"
    assert user.contraintes_sante_json == '["cardiaque"]'

    bio = db_session.query(MesureBiometrique).filter_by(utilisateur_id=user.utilisateur_id).one()
    assert bio.poids_kg == pytest.approx(55, abs=0.01)
    assert bio.taille_cm == pytest.approx(155, abs=0.01)
    assert bio.imc == pytest.approx(22.89, abs=0.01)

    objective = db_session.query(ObjectifUtilisateur).filter_by(utilisateur_id=user.utilisateur_id).one()
    assert objective.type_objectif == "GAIN_MUSCLE"
    assert objective.poids_cible_kg == pytest.approx(62.9, abs=0.01)
    assert objective.actif_unique is True


def test_register_complete_rejects_duplicate_email_and_username(client: TestClient, db_session: Session):
    first = client.post("/api/auth/register-complete", json=complete_register_payload(username="unique-one", email="unique-one@example.test"))
    assert first.status_code == 201

    duplicate_username = client.post(
        "/api/auth/register-complete",
        json=complete_register_payload(username="unique-one", email="unique-two@example.test"),
    )
    duplicate_email = client.post(
        "/api/auth/register-complete",
        json=complete_register_payload(username="unique-three", email="unique-one@example.test"),
    )

    assert duplicate_username.status_code == 409
    assert duplicate_username.json()["error"]["code"] == "username_taken"
    assert duplicate_email.status_code == 409
    assert duplicate_email.json()["error"]["code"] == "email_taken"
    assert db_session.scalar(
        select(func.count(Utilisateur.utilisateur_id)).where(Utilisateur.email == "unique-one@example.test")
    ) == 1


def test_register_complete_rolls_back_when_linked_profile_fails(client: TestClient, db_session: Session):
    payload = complete_register_payload(
        username="rollback-user",
        email="rollback-user@example.test",
        objectif="OBJECTIF_IMPOSSIBLE",
    )

    response = client.post("/api/auth/register-complete", json=payload)

    assert response.status_code == 422
    user_id = db_session.scalar(
        select(Utilisateur.utilisateur_id).where(Utilisateur.nom_utilisateur == "rollback-user")
    )
    assert user_id is None
    assert db_session.scalar(select(func.count(MesureBiometrique.mesure_id))) == 0
    assert db_session.scalar(select(func.count(ObjectifUtilisateur.objectif_id))) == 0
    assert db_session.scalar(select(func.count(MesureSommeilSante.mesure_sommeil_id))) == 0


def test_profile_and_dashboards_smoke(client: TestClient):
    user_headers = auth_headers(client, "alice", "secret")
    admin_headers = auth_headers(client)
    super_headers = auth_headers(client, "superadmin", "superadmin-secret")

    assert client.get("/api/me/profile", headers=user_headers).status_code == 200
    assert client.get("/api/me/dashboard", headers=user_headers).status_code == 200
    assert client.get("/api/admin/dashboard/kpis", headers=admin_headers).status_code == 200
    assert client.get("/api/admin/qualite/kpis", headers=admin_headers).status_code == 200
    assert client.get("/api/super-admin/monitoring/etl", headers=super_headers).status_code == 200


def test_avatar_upload_replace_and_delete(client: TestClient, tmp_path, monkeypatch: pytest.MonkeyPatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "media_root", str(tmp_path), raising=False)
    monkeypatch.setattr(settings, "media_base_url", "http://testserver", raising=False)
    headers = auth_headers(client, "alice", "secret")
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
    webp = b"RIFF" + (b"\x00" * 4) + b"WEBP" + (b"\x00" * 24)

    created = client.post(
        "/api/me/avatar",
        headers=headers,
        files={"file": ("avatar.png", png, "image/png")},
    )

    assert created.status_code == 201
    data = created.json()["data"]
    assert data["photo_profil_path"].startswith("uploads/avatars/user-")
    assert data["photo_profil_url"].startswith("http://testserver/media/avatars/")
    first_path = tmp_path / data["photo_profil_path"]
    assert first_path.is_file()

    replaced = client.put(
        "/api/me/avatar",
        headers=headers,
        files={"file": ("avatar.webp", webp, "image/webp")},
    )

    assert replaced.status_code == 200
    replaced_data = replaced.json()["data"]
    assert replaced_data["photo_profil_path"].endswith(".webp")
    assert not first_path.exists()

    deleted = client.delete("/api/me/avatar", headers=headers)

    assert deleted.status_code == 200
    assert deleted.json()["data"]["photo_profil_path"] is None
    assert deleted.json()["data"]["photo_profil_url"] is None


def test_avatar_rejects_invalid_file_type(client: TestClient, tmp_path, monkeypatch: pytest.MonkeyPatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "media_root", str(tmp_path), raising=False)
    headers = auth_headers(client, "alice", "secret")

    response = client.post(
        "/api/me/avatar",
        headers=headers,
        files={"file": ("avatar.txt", b"not an image", "text/plain")},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"

    spoofed = client.post(
        "/api/me/avatar",
        headers=headers,
        files={"file": ("avatar.png", b"not really a png", "image/png")},
    )

    assert spoofed.status_code == 422
    assert spoofed.json()["error"]["code"] == "validation_error"


def test_onboarding_creates_records_without_duplicates(client: TestClient, db_session: Session):
    headers = auth_headers(client, "alice", "secret")
    payload = {
        "prenom": "Alice",
        "nom": "Martin",
        "date_naissance": "1992-03-14",
        "genre": "Femme",
        "taille_cm": 168,
        "poids_actuel_kg": 71.5,
        "poids_cible_kg": 66,
        "objectif_principal": "perte de poids",
        "niveau_activite": "modere",
        "niveau_sportif": "intermediaire",
        "allergies": ["arachide"],
        "regime_alimentaire": "vegetarien",
        "preferences_alimentaires": ["riz", "legumes"],
        "aliments_evites": ["thon"],
        "budget": "moyen",
        "equipements": ["tapis", "halteres"],
        "contraintes_sante": ["douleur genou"],
        "preferences_sportives": ["gainage"],
        "frequence_seances_hebdo": 3,
        "duree_seance_min": 45,
        "duree_sommeil_h": 7.5,
        "qualite_sommeil_score": 8,
    }

    response = client.post("/api/me/onboarding", headers=headers, json=payload)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["onboarding_complete"] is True
    assert data["photo_profil_url"] is None
    assert data["niveau_sportif"] == "intermediaire"

    alice = db_session.query(Utilisateur).filter_by(nom_utilisateur="alice").one()
    assert alice.prenom == "Alice"
    assert alice.onboarding_complete is True
    assert alice.allergies_json == '["arachide"]'

    bio_count = db_session.scalar(
        select(func.count(MesureBiometrique.mesure_id)).where(
            MesureBiometrique.utilisateur_id == alice.utilisateur_id,
            MesureBiometrique.source_id.is_(None),
            MesureBiometrique.lot_id.is_(None),
        )
    )
    sleep_count = db_session.scalar(
        select(func.count(MesureSommeilSante.mesure_sommeil_id)).where(
            MesureSommeilSante.utilisateur_id == alice.utilisateur_id,
            MesureSommeilSante.source_id.is_(None),
            MesureSommeilSante.lot_id.is_(None),
        )
    )
    objective_count = db_session.scalar(
        select(func.count(ObjectifUtilisateur.objectif_id)).where(
            ObjectifUtilisateur.utilisateur_id == alice.utilisateur_id,
            ObjectifUtilisateur.actif_unique.is_(True),
        )
    )
    assert bio_count == 1
    assert sleep_count == 1
    assert objective_count == 1

    payload["poids_actuel_kg"] = 70
    second = client.post("/api/me/onboarding", headers=headers, json=payload)
    assert second.status_code == 200

    assert db_session.scalar(
        select(func.count(MesureBiometrique.mesure_id)).where(
            MesureBiometrique.utilisateur_id == alice.utilisateur_id,
            MesureBiometrique.source_id.is_(None),
            MesureBiometrique.lot_id.is_(None),
        )
    ) == 1


def test_collection_response_is_paginated(client: TestClient):
    response = client.get("/api/organisations?page=1&page_size=1", headers=auth_headers(client))

    assert response.status_code == 200
    body = response.json()
    assert {"data", "meta"}.issubset(body.keys())
    assert body["meta"] == {"page": 1, "page_size": 1, "total": 1, "total_pages": 1}


def test_role_guard_blocks_regular_user_from_admin_dashboard(client: TestClient):
    response = client.get("/api/admin/dashboard", headers=auth_headers(client, "alice", "secret"))

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_me_routes_are_scoped_to_authenticated_user(client: TestClient, db_session: Session):
    alice = db_session.query(Utilisateur).filter_by(nom_utilisateur="alice").one()
    admin = db_session.query(Utilisateur).filter_by(nom_utilisateur="admin").one()
    db_session.add_all(
        [
            Plat(utilisateur_id=alice.utilisateur_id, consomme_le=datetime.now(timezone.utc), type_repas="DEJEUNER"),
            Plat(utilisateur_id=admin.utilisateur_id, consomme_le=datetime.now(timezone.utc), type_repas="DINER"),
        ]
    )
    db_session.commit()

    response = client.get("/api/me/plats", headers=auth_headers(client, "alice", "secret"))

    assert response.status_code == 200
    rows = response.json()["data"]
    assert len(rows) == 1
    assert rows[0]["utilisateur_id"] == alice.utilisateur_id


def test_journal_alimentaire_creation_requires_plat_xor_aliment(client: TestClient, db_session: Session):
    alice = db_session.query(Utilisateur).filter_by(nom_utilisateur="alice").one()

    response = client.post(
        "/api/journal-alimentaire",
        headers=auth_headers(client),
        json={
            "utilisateur_id": alice.utilisateur_id,
            "consomme_le": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
            "type_repas": "DEJEUNER",
            "plat_id": 1,
            "aliment_id": 1,
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_delete_returns_conflict_when_dependencies_exist(client: TestClient, db_session: Session):
    alice = db_session.query(Utilisateur).filter_by(nom_utilisateur="alice").one()
    db_session.add(Plat(utilisateur_id=alice.utilisateur_id, consomme_le=datetime.now(timezone.utc), type_repas="DEJEUNER"))
    db_session.commit()

    response = client.delete(f"/api/utilisateurs/{alice.utilisateur_id}", headers=auth_headers(client))

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


def test_meal_analysis_returns_structured_fallback_when_ai_is_not_configured(client: TestClient):
    response = client.post(
        "/api/me/analyse-plat",
        headers=auth_headers(client, "alice", "secret"),
        json={"image_base64": TINY_PNG_DATA_URL, "mime_type": "image/png"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["plat_detecte"]
    assert data["source_analyse"] == "local_mock"
    assert data["mode"] == "mock"
    assert isinstance(data["aliments_detectes"], list)
    assert isinstance(data["portions_estimees"], list)
    assert isinstance(data["hypotheses"], list)
    assert "proteines_g" in data["macronutriments"]
    assert "raw_vision_predictions" in data


def test_meal_analysis_config_route_exposes_flags_without_token(client: TestClient):
    response = client.get("/api/me/analyse-plat/config", headers=auth_headers(client, "alice", "secret"))

    assert response.status_code == 200
    data = response.json()["data"]
    assert set(data.keys()) == {
        "external_ai_enabled",
        "force_mock",
        "huggingface_configured",
        "deepseek_configured",
        "vision_model",
        "vision_fallback_models",
        "provider",
    }
    assert isinstance(data["huggingface_configured"], bool)


def test_recommendations_apply_allergy_and_equipment_guards(client: TestClient, db_session: Session):
    db_session.add_all(
        [
            Aliment(
                nom="Beurre de cacahuete",
                categorie="Tartinable",
                calories_kcal=588,
                proteines_g=25,
                glucides_g=20,
                lipides_g=50,
            ),
            Aliment(
                nom="Riz complet",
                categorie="Cereales",
                calories_kcal=120,
                proteines_g=3,
                glucides_g=25,
                lipides_g=1,
                fibres_g=2,
            ),
            Exercice(
                nom="Curl halteres",
                body_part_principale="upper arms",
                muscle_cible_principal="biceps",
                equipement_principal="dumbbell",
            ),
            Exercice(
                nom="Gainage",
                body_part_principale="waist",
                muscle_cible_principal="abs",
                equipement_principal="body weight",
            ),
        ]
    )
    db_session.commit()

    response = client.post(
        "/api/me/recommandations",
        headers=auth_headers(client, "alice", "secret"),
        json={
            "objectif_principal": "sante",
            "allergies": ["arachide"],
            "equipement_disponible": [],
            "max_nutrition": 5,
            "max_sport": 5,
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["fallback_utilise"] is True
    assert all("cacahuete" not in item["nom"].lower() for item in data["nutrition"])
    assert all(
        "dumbbell" not in " ".join(item["equipement_necessaire"]).lower()
        for item in data["sport"]["exercices"]
    )


def test_recommendations_use_profile_defaults_and_keep_user_isolation(client: TestClient, db_session: Session):
    db_session.add_all(
        [
            Aliment(
                nom="Beurre de cacahuete",
                categorie="Tartinable",
                calories_kcal=588,
                proteines_g=25,
                glucides_g=20,
                lipides_g=50,
            ),
            Aliment(
                nom="Riz complet",
                categorie="Cereales",
                calories_kcal=120,
                proteines_g=3,
                glucides_g=25,
                lipides_g=1,
                fibres_g=2,
            ),
            Exercice(
                nom="Curl halteres",
                body_part_principale="upper arms",
                muscle_cible_principal="biceps",
                equipement_principal="dumbbell",
            ),
            Exercice(
                nom="Gainage",
                body_part_principale="waist",
                muscle_cible_principal="abs",
                equipement_principal="body weight",
            ),
        ]
    )
    db_session.commit()

    protected = client.post(
        "/api/auth/register-complete",
        json={
            **complete_register_payload(username="protected-user", email="protected@example.test"),
            "equipements": ["tapis"],
        },
    )
    assert protected.status_code == 201
    protected_headers = {"Authorization": f"Bearer {protected.json()['data']['access_token']}"}

    open_payload = complete_register_payload(username="open-user", email="open@example.test")
    open_payload["allergies"] = ["aucune"]
    open_payload["equipements"] = ["halteres"]
    open_payload["contraintes_sante"] = ["aucune"]
    open_response = client.post("/api/auth/register-complete", json=open_payload)
    assert open_response.status_code == 201
    open_headers = {"Authorization": f"Bearer {open_response.json()['data']['access_token']}"}

    protected_recs = client.post("/api/me/recommandations", headers=protected_headers, json={})
    open_recs = client.post("/api/me/recommandations", headers=open_headers, json={})

    assert protected_recs.status_code == 200
    protected_data = protected_recs.json()["data"]
    assert protected_data["contexte"]["utilisateur_id"] != open_recs.json()["data"]["contexte"]["utilisateur_id"]
    assert any("allergies: arachide" in item for item in protected_data["contraintes_prises_en_compte"])
    assert any("equipement: tapis" in item for item in protected_data["contraintes_prises_en_compte"])
    assert all("cacahuete" not in item["nom"].lower() for item in protected_data["nutrition"])
    assert all(
        "dumbbell" not in " ".join(item["equipement_necessaire"]).lower()
        for item in protected_data["sport"]["exercices"]
    )

    assert open_recs.status_code == 200
    open_data = open_recs.json()["data"]
    assert any("cacahuete" in item["nom"].lower() for item in open_data["nutrition"])
    assert any(
        "dumbbell" in " ".join(item["equipement_necessaire"]).lower()
        for item in open_data["sport"]["exercices"]
    )

    no_equipment_recs = client.post(
        "/api/me/recommandations",
        headers=open_headers,
        json={"equipement_disponible": [], "max_sport": 5},
    )
    assert no_equipment_recs.status_code == 200
    no_equipment_data = no_equipment_recs.json()["data"]
    assert all(
        "dumbbell" not in " ".join(item["equipement_necessaire"]).lower()
        for item in no_equipment_data["sport"]["exercices"]
    )


def test_meal_analysis_rejects_invalid_base64(client: TestClient):
    response = client.post(
        "/api/me/analyse-plat",
        headers=auth_headers(client, "alice", "secret"),
        json={"image_base64": "not-a-valid-image"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_meal_analysis_uses_huggingface_predictions_when_configured(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
):
    settings = get_settings()
    monkeypatch.setattr(settings, "ai_enable_external_calls", True, raising=False)
    monkeypatch.setattr(settings, "meal_ai_force_mock", False, raising=False)
    monkeypatch.setattr(settings, "hf_token", "hf_test_token", raising=False)
    monkeypatch.setattr(settings, "huggingface_api_token", None, raising=False)
    monkeypatch.setattr(settings, "huggingface_vision_model", "nateraw/food", raising=False)

    db_session.add(
        Aliment(
            nom="pizza",
            calories_kcal=250,
            proteines_g=11,
            glucides_g=30,
            lipides_g=10,
            fibres_g=2,
            sucres_g=3,
            sodium_mg=450,
            cholesterol_mg=20,
        )
    )
    db_session.commit()

    class FakeInferenceClient:
        def __init__(self, *args, **kwargs):
            pass

        def image_classification(self, *args, **kwargs):
            return [
                {"label": "pizza", "score": 0.82},
                {"label": "omelette", "score": 0.11},
            ]

    monkeypatch.setattr("app.services.meal_analysis.InferenceClient", FakeInferenceClient)

    response = client.post(
        "/api/me/analyse-plat",
        headers=auth_headers(client, "alice", "secret"),
        json={"image_base64": TINY_PNG_DATA_URL, "mime_type": "image/png"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["mode"] == "external"
    assert data["source_analyse"] == "huggingface_plus_local_reasoning"
    assert data["raw_vision_predictions"][0]["label"] == "pizza"
    assert data["aliments_detectes"][0]["matched_aliment_nom"] == "pizza"


def test_coach_posture_feedback_returns_local_response(client: TestClient):
    response = client.post(
        "/api/me/coach-posture/feedback",
        headers=auth_headers(client, "alice", "secret"),
        json={
            "exercise": "squat",
            "status": "almost",
            "angles": {"left_knee": 95, "right_knee": 98, "left_hip": 80},
            "detected_errors": ["dos trop penche"],
            "reps": 4,
            "reps_in_current_set": 4,
            "sets": 0,
            "hold_seconds": 0,
            "best_hold_seconds": 0,
            "validated_holds": [],
            "score_alignement": 72,
            "person_detected": True,
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["mode"] == "local"
    assert data["exercise"] == "squat"
    assert data["statut_posture"] == "almost"
    assert data["repetitions"] == 4
    assert data["score_alignement"] == 72


def test_coach_posture_validate_dynamic_payload_creates_history_entry(client: TestClient, db_session: Session):
    response = client.post(
        "/api/me/coach-posture/validate",
        headers=auth_headers(client, "alice", "secret"),
        json={
            "exercise": "curl_biceps",
            "exercise_label": "Curl biceps",
            "type": "dynamic",
            "reps": 12,
            "reps_in_current_set": 2,
            "sets": 1,
            "hold_seconds": 0,
            "best_hold_seconds": 0,
            "validated_holds": 0,
            "score_alignement": 82,
            "status": "correct",
            "detected_errors": [],
            "feedback": {"mode": "local"},
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["saved"] is True
    assert data["exercise"] == "curl_biceps"
    assert data["item"]["coach_posture_id"]
    assert data["summary"]["reps"] == 12
    assert data["summary"]["exercise"] == "curl_biceps"
    assert data["summary"]["type"] == "dynamic"
    assert db_session.get(CoachPostureSession, int(data["validation_id"])) is not None


def test_coach_posture_validate_static_payload_creates_history_entry(client: TestClient, db_session: Session):
    response = client.post(
        "/api/me/coach-posture/validate",
        headers=auth_headers(client, "alice", "secret"),
        json={
            "exercise": "wall_sit",
            "exercise_label": "Chaise contre mur",
            "type": "static",
            "reps": 0,
            "reps_in_current_set": 0,
            "sets": 1,
            "hold_seconds": 45,
            "best_hold_seconds": 45,
            "validated_holds": 1,
            "score_alignement": 84,
            "status": "correct",
            "detected_errors": [],
            "snapshot_base64": TINY_PNG_DATA_URL,
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["saved"] is True
    assert data["item"]["validated_holds"] == 1
    assert data["summary"]["sets"] == 1
    assert data["summary"]["hold_seconds"] == 45
    assert data["summary"]["type"] == "static"


def test_coach_posture_validate_tree_pose_static_payload(client: TestClient):
    response = client.post(
        "/api/me/coach-posture/validate",
        headers=auth_headers(client, "alice", "secret"),
        json={
            "exercise": "tree_pose",
            "exercise_label": "Posture de l'arbre",
            "type": "static",
            "reps": 0,
            "reps_in_current_set": 0,
            "sets": 1,
            "hold_seconds": 32,
            "best_hold_seconds": 32,
            "validated_holds": 1,
            "score_alignement": 79,
            "status": "correct",
            "detected_errors": [],
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["saved"] is True
    assert data["summary"]["exercise"] == "tree_pose"
    assert data["summary"]["hold_seconds"] == 32


def test_coach_posture_history_returns_recent_validations(client: TestClient):
    headers = auth_headers(client, "alice", "secret")
    response = client.post(
        "/api/me/coach-posture/validate",
        headers=headers,
        json={
            "exercise": "curl_biceps",
            "exercise_label": "Curl biceps",
            "type": "dynamic",
            "reps": 12,
            "reps_in_current_set": 0,
            "sets": 1,
            "hold_seconds": 0,
            "best_hold_seconds": 0,
            "validated_holds": 0,
            "score_alignement": 88,
            "status": "correct",
            "detected_errors": [],
        },
    )
    assert response.status_code == 200

    history = client.get("/api/me/coach-posture/history", headers=headers)

    assert history.status_code == 200
    rows = history.json()["data"]
    assert rows
    assert rows[0]["exercise"] == "curl_biceps"
    assert rows[0]["exercise_label"] == "Curl biceps"
    assert rows[0]["summary"]["reps"] == 12
    assert rows[0]["item"]["coach_posture_id"]
    assert rows[0]["saved"] is True
