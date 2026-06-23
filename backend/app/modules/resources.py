from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Body, Depends, Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError, create_model, model_validator
from sqlalchemy import Column, Select, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ApiError
from app.core.pagination import (
    PaginationParams,
    apply_search,
    apply_sort,
    filters_echo,
    paginated_response,
    pagination_params,
)
from app.core.security import current_user, require_roles
from app.db.models import Aliment, Organisation, SourceDonnees, Utilisateur
from app.db.session import get_db


CRUD_ROLES = ("ADMIN", "SUPER_ADMIN")


@dataclass(frozen=True)
class ResourceConfig:
    path: str
    model: type
    pk: str
    owner_field: str | None = None
    soft_delete_field: str | None = None
    soft_delete_value: Any = None
    create_schema: type[BaseModel] | None = None
    update_schema: type[BaseModel] | None = None
    sortable_fields: tuple[str, ...] = ()
    searchable_fields: tuple[str, ...] = ()


MEDIA_PATH_RULES: dict[tuple[str, str], tuple[str, str]] = {
    # (table, column) -> (mount kind, companion field name)
    ("exercice", "gif_180_path"): ("exercises", "gif_180_url"),
    ("exercice", "gif_360_path"): ("exercises", "gif_360_url"),
    ("exercice", "gif_720_path"): ("exercises", "gif_720_url"),
    ("exercice", "gif_1080_path"): ("exercises", "gif_1080_url"),
    ("organisation", "image_path"): ("organisations", "image_url"),
    ("progression_photo", "image_path"): ("progression", "photo_url"),
    ("utilisateur", "photo_profil_path"): ("avatars", "photo_profil_url"),
}


def media_url(kind: str, value: str | None) -> str | None:
    if not value:
        return None
    # Handle already-formed URLs
    if value.startswith(("http://", "https://", "/media/")):
        return value
    # Normalize Windows paths to forward slashes
    normalized = value.replace("\\", "/")
    source_markers = {
        "exercises": "exercisedb_v1_sample/",
        "organisations": "organisme/",
        "progression": "before after/",
        "avatars": "uploads/avatars/",
    }
    marker = source_markers.get(kind)
    if marker and marker in normalized:
        normalized = normalized.split(marker, 1)[1]
    normalized = normalized.lstrip("/")
    base = get_settings().media_base_url.rstrip("/")
    return f"{base}/media/{kind}/{normalized}"


def serialize_model(obj: Any, hide_sensitive: bool = True) -> dict[str, Any]:
    table_name = obj.__table__.name
    data: dict[str, Any] = {}
    for column in obj.__table__.columns:
        data[column.name] = getattr(obj, column.name)
    for column in obj.__table__.columns:
        rule = MEDIA_PATH_RULES.get((table_name, column.name))
        if rule:
            kind, url_field = rule
            url = media_url(kind, data[column.name])
            data[url_field] = url
            if table_name == "progression_photo" and column.name == "image_path":
                # Backward-compatible alias: old frontend code used image_url.
                data["image_url"] = url
    if hide_sensitive:
        data.pop("mot_de_passe_hash", None)
    return data


def _python_type(column: Column[Any]) -> type[Any]:
    try:
        py_type = column.type.python_type
    except NotImplementedError:
        py_type = str
    return py_type


def build_schema(name: str, model: type, *, partial: bool) -> type[BaseModel]:
    fields: dict[str, tuple[Any, Any]] = {}
    for column in model.__table__.columns:
        if column.primary_key or column.name in {"cree_le", "modifie_le", "mot_de_passe_hash"}:
            continue
        py_type = _python_type(column)
        annotation = py_type | None
        default = None if partial or column.nullable or column.default is not None else ...
        fields[column.name] = (annotation, default)

    schema = create_model(
        name,
        __config__=ConfigDict(extra="ignore", from_attributes=True),
        **fields,
    )
    # Fix ForwardRef serialization by properly setting module context
    schema.__module__ = __name__
    # Rebuild the model to resolve any forward references
    try:
        schema.model_rebuild()
    except Exception:
        pass  # If rebuild fails, continue anyway
    return schema


class JournalAlimentaireCreate(BaseModel):
    utilisateur_id: int
    plat_id: int | None = None
    aliment_id: int | None = None
    source_id: int | None = None
    lot_id: int | None = None
    consomme_le: datetime
    type_repas: str | None = None
    aliment_nom_libre: str | None = None
    quantite: float | None = None
    unite_quantite: str | None = None
    calories_kcal: float | None = None
    eau_ml: float | None = None

    @model_validator(mode="after")
    def validate_reference(self) -> JournalAlimentaireCreate:
        if (self.plat_id is None) == (self.aliment_id is None):
            raise ValueError("Une ligne doit referencer soit un plat, soit un aliment.")
        return self


class JournalAlimentaireUpdate(BaseModel):
    utilisateur_id: int | None = None
    plat_id: int | None = None
    aliment_id: int | None = None
    source_id: int | None = None
    lot_id: int | None = None
    consomme_le: datetime | None = None
    type_repas: str | None = None
    aliment_nom_libre: str | None = None
    quantite: float | None = None
    unite_quantite: str | None = None
    calories_kcal: float | None = None
    eau_ml: float | None = None

    @model_validator(mode="after")
    def validate_reference(self) -> JournalAlimentaireUpdate:
        if self.plat_id is not None and self.aliment_id is not None:
            raise ValueError("Une ligne doit referencer soit un plat, soit un aliment.")
        return self


class SeanceCompleteCreate(BaseModel):
    utilisateur_id: int
    source_id: int | None = None
    lot_id: int | None = None
    date_seance: datetime
    type_entrainement: str | None = None
    duree_seance_min: int | None = None
    calories_brulees_total: float | None = None
    frequence_entrainement_j_sem: int | None = None
    niveau_experience: str | None = None
    eau_l: float | None = None
    exercices: list[dict[str, Any]] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_details(self) -> SeanceCompleteCreate:
        if "exercices" in self.model_fields_set and not self.exercices:
            raise ValueError("Une seance creee avec detail complet doit contenir au moins un exercice.")
        return self


def _base_query(model: type, owner_field: str | None, user: Utilisateur) -> Select[Any]:
    stmt = select(model)
    if owner_field and user.role == "UTILISATEUR":
        stmt = stmt.where(getattr(model, owner_field) == user.utilisateur_id)
    return stmt


def create_crud_router(config: ResourceConfig) -> APIRouter:
    router = APIRouter(prefix=config.path, tags=[config.path.strip("/")])
    create_schema = config.create_schema or build_schema(f"{config.model.__name__}Create", config.model, partial=False)
    update_schema = config.update_schema or build_schema(f"{config.model.__name__}Update", config.model, partial=True)
    pk_column = getattr(config.model, config.pk)

    sortable = config.sortable_fields or (config.pk,)

    @router.get("")
    def list_items(
        pagination: PaginationParams = Depends(pagination_params),
        role: str | None = None,
        statut: str | None = None,
        actif: str | None = None,
        severite: str | None = None,
        entite: str | None = None,
        body_part_principale: str | None = None,
        muscle_cible_principal: str | None = None,
        equipement_principal: str | None = None,
        categorie: str | None = None,
        organisation_id: int | None = None,
        db: Session = Depends(get_db),
        user: Utilisateur = Depends(current_user),
    ) -> dict[str, Any]:
        stmt = _base_query(config.model, config.owner_field, user)
        extra_filters: dict[str, Any] = {}
        if role and hasattr(config.model, "role"):
            stmt = stmt.where(getattr(config.model, "role") == role)
            extra_filters["role"] = role
        if statut and hasattr(config.model, "statut"):
            stmt = stmt.where(getattr(config.model, "statut") == statut)
            extra_filters["statut"] = statut
        if actif is not None and actif != "" and hasattr(config.model, "actif"):
            actif_bool = str(actif).lower() in {"1", "true", "yes", "on"}
            stmt = stmt.where(getattr(config.model, "actif") == actif_bool)
            extra_filters["actif"] = actif_bool
        if severite and hasattr(config.model, "severite"):
            stmt = stmt.where(getattr(config.model, "severite") == severite)
            extra_filters["severite"] = severite
        if entite and hasattr(config.model, "entite"):
            stmt = stmt.where(getattr(config.model, "entite") == entite)
            extra_filters["entite"] = entite
        for field, value in {
            "body_part_principale": body_part_principale,
            "muscle_cible_principal": muscle_cible_principal,
            "equipement_principal": equipement_principal,
            "categorie": categorie,
            "organisation_id": organisation_id,
        }.items():
            if value not in (None, "") and hasattr(config.model, field):
                stmt = stmt.where(getattr(config.model, field) == value)
                extra_filters[field] = value
        stmt = apply_search(stmt, config.model, pagination, searchable=config.searchable_fields)
        stmt = apply_sort(stmt, config.model, pagination, sortable=sortable, default_field=config.pk)
        total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        rows = db.execute(stmt.offset(pagination.offset).limit(pagination.page_size)).scalars().all()
        return paginated_response(
            [serialize_model(row) for row in rows],
            pagination.page,
            pagination.page_size,
            int(total),
            filters=filters_echo(pagination, extra_filters),
        )

    @router.get("/{item_id}")
    def get_item(
        item_id: int,
        db: Session = Depends(get_db),
        user: Utilisateur = Depends(current_user),
    ) -> dict[str, Any]:
        item = db.get(config.model, item_id)
        if not item:
            raise ApiError(404, "not_found", "Ressource introuvable.")
        if config.owner_field and user.role == "UTILISATEUR" and getattr(item, config.owner_field) != user.utilisateur_id:
            raise ApiError(403, "forbidden", "Acces refuse a cette ressource.")
        return {"data": serialize_model(item)}

    @router.post("", status_code=201)
    def create_item(
        payload: Any = Body(default=None),
        db: Session = Depends(get_db),
        user: Utilisateur = Depends(current_user),
    ) -> dict[str, Any]:
        if user.role not in CRUD_ROLES and not config.owner_field:
            raise ApiError(403, "forbidden", "Acces refuse.")
        # Validate payload using the schema
        try:
            validated = create_schema(**payload) if isinstance(payload, dict) else payload
        except ValidationError as exc:
            raise ApiError(
                422,
                "validation_error",
                "La requete est invalide.",
                exc.errors(include_context=False),
            ) from exc
        data = validated.model_dump(exclude_unset=True)
        if user.role == "UTILISATEUR" and config.owner_field:
            data[config.owner_field] = user.utilisateur_id
        data.setdefault("cree_le", datetime.utcnow())
        item = config.model(**data)
        try:
            db.add(item)
            db.commit()
            db.refresh(item)
        except IntegrityError:
            db.rollback()
            raise
        return {"data": serialize_model(item)}

    @router.patch("/{item_id}")
    def update_item(
        item_id: int,
        payload: Any = Body(default=None),
        db: Session = Depends(get_db),
        user: Utilisateur = Depends(current_user),
    ) -> dict[str, Any]:
        if user.role not in CRUD_ROLES and not config.owner_field:
            raise ApiError(403, "forbidden", "Acces refuse.")
        # Validate payload using the schema
        try:
            validated = update_schema(**payload) if isinstance(payload, dict) else payload
        except ValidationError as exc:
            raise ApiError(
                422,
                "validation_error",
                "La requete est invalide.",
                exc.errors(include_context=False),
            ) from exc
        item = db.get(config.model, item_id)
        if not item:
            raise ApiError(404, "not_found", "Ressource introuvable.")
        if user.role == "UTILISATEUR" and config.owner_field and getattr(item, config.owner_field) != user.utilisateur_id:
            raise ApiError(403, "forbidden", "Ressource non autorisee.")
        for key, value in validated.model_dump(exclude_unset=True).items():
            if user.role == "UTILISATEUR" and config.owner_field and key == config.owner_field:
                continue
            setattr(item, key, value)
        if hasattr(item, "modifie_le"):
            item.modifie_le = datetime.utcnow()
        db.commit()
        db.refresh(item)
        return {"data": serialize_model(item)}

    @router.put("/{item_id}")
    def replace_item(
        item_id: int,
        payload: Any = Body(default=None),
        db: Session = Depends(get_db),
        _: Utilisateur = Depends(require_roles(*CRUD_ROLES)),
    ) -> dict[str, Any]:
        # Validate payload using the schema
        try:
            validated = create_schema(**payload) if isinstance(payload, dict) else payload
        except ValidationError as exc:
            raise ApiError(
                422,
                "validation_error",
                "La requete est invalide.",
                exc.errors(include_context=False),
            ) from exc
        item = db.get(config.model, item_id)
        if not item:
            raise ApiError(404, "not_found", "Ressource introuvable.")
        for key, value in validated.model_dump(exclude_unset=True).items():
            setattr(item, key, value)
        if hasattr(item, "modifie_le"):
            item.modifie_le = datetime.utcnow()
        db.commit()
        db.refresh(item)
        return {"data": serialize_model(item)}

    @router.delete("/{item_id}")
    def delete_item(
        item_id: int,
        db: Session = Depends(get_db),
        user: Utilisateur = Depends(current_user),
    ) -> dict[str, Any]:
        if user.role not in CRUD_ROLES and not config.owner_field:
            raise ApiError(403, "forbidden", "Acces refuse.")
        if config.model is Utilisateur and item_id == user.utilisateur_id:
            raise ApiError(403, "forbidden", "Vous ne pouvez pas supprimer votre propre compte.")
        item = db.get(config.model, item_id)
        if not item:
            raise ApiError(404, "not_found", "Ressource introuvable.")
        if config.model is Organisation and item_id == user.organisation_id:
            raise ApiError(409, "conflict", "Impossible de supprimer votre organisation courante.")
        if user.role == "UTILISATEUR" and config.owner_field and getattr(item, config.owner_field) != user.utilisateur_id:
            raise ApiError(403, "forbidden", "Ressource non autorisee.")
        if _has_blocking_dependencies(db, config.model, config.pk, item_id):
            if config.soft_delete_field:
                setattr(item, config.soft_delete_field, config.soft_delete_value)
                db.commit()
                return {
                    "data": {
                        "success": True,
                        "deleted": False,
                        "deactivated": True,
                        "message": _deactivated_message(config.model),
                    }
                }
            raise ApiError(409, "conflict", _blocking_message(config.model))
        try:
            db.delete(item)
            db.commit()
            return {
                "data": {
                    "success": True,
                    "deleted": True,
                    "deactivated": False,
                    "message": _deleted_message(config.model),
                }
            }
        except IntegrityError:
            db.rollback()
            if config.soft_delete_field:
                setattr(item, config.soft_delete_field, config.soft_delete_value)
                db.commit()
                return {
                    "data": {
                        "success": True,
                        "deleted": False,
                        "deactivated": True,
                        "message": _deactivated_message(config.model),
                    }
                }
            raise ApiError(409, "conflict", _blocking_message(config.model))

    return router


def _has_blocking_dependencies(db: Session, model: type, pk: str, value: int) -> bool:
    for table in model.metadata.sorted_tables:
        if table.name == model.__tablename__:
            continue
        for fk in table.foreign_keys:
            if fk.column.table.name == model.__tablename__ and fk.column.name == pk:
                exists_stmt = select(table.c[fk.parent.name]).where(table.c[fk.parent.name] == value).limit(1)
                if db.execute(exists_stmt).first() is not None:
                    return True
    return False


def _deleted_message(model: type) -> str:
    if model is Aliment:
        return "Aliment supprime."
    if model is Organisation:
        return "Organisation supprimee."
    if model is SourceDonnees:
        return "Source supprimee."
    return "Ressource supprimee."


def _deactivated_message(model: type) -> str:
    if model is SourceDonnees:
        return "Source liee a des donnees : elle a ete desactivee."
    return "Ressource desactivee car des dependances existent."


def _blocking_message(model: type) -> str:
    if model is Aliment:
        return "Impossible de supprimer cet aliment car il est utilise dans un journal alimentaire."
    if model is Organisation:
        return "Impossible de supprimer cette organisation car elle contient des utilisateurs."
    if model is SourceDonnees:
        return "Impossible de supprimer cette source car elle est liee a des donnees existantes."
    return "Suppression refusee: dependances existantes."
