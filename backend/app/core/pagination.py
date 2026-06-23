from __future__ import annotations

from math import ceil
from typing import Any, Literal

from fastapi import Query
from pydantic import BaseModel
from sqlalchemy import Select, or_


SortOrder = Literal["asc", "desc"]


class PaginationParams(BaseModel):
    page: int = 1
    page_size: int = 20
    sort_by: str | None = None
    sort_order: SortOrder = "desc"
    search: str | None = None

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def pagination_params(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str | None = Query(None, description="Colonne de tri (whitelist par ressource)."),
    sort_order: SortOrder = Query("desc"),
    search: str | None = Query(None, min_length=1, max_length=100),
    q: str | None = Query(None, min_length=1, max_length=100),
) -> PaginationParams:
    return PaginationParams(
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
        search=search or q,
    )


def paginated_response(
    data: list[Any],
    page: int,
    page_size: int,
    total: int,
    *,
    filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "data": data,
        "meta": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": ceil(total / page_size) if total else 0,
        },
        "filters": filters or {},
    }


def apply_sort(
    stmt: Select[Any],
    model: type,
    pagination: PaginationParams,
    *,
    sortable: tuple[str, ...],
    default_field: str,
) -> Select[Any]:
    """Apply sort_by/sort_order with whitelist; fall back to default_field desc."""
    field = pagination.sort_by if pagination.sort_by in sortable else default_field
    column = getattr(model, field)
    return stmt.order_by(column.asc() if pagination.sort_order == "asc" else column.desc())


def apply_search(
    stmt: Select[Any],
    model: type,
    pagination: PaginationParams,
    *,
    searchable: tuple[str, ...],
) -> Select[Any]:
    """Apply LIKE search on whitelisted text fields."""
    if not pagination.search or not searchable:
        return stmt
    pattern = f"%{pagination.search}%"
    clauses = [getattr(model, field).ilike(pattern) for field in searchable if hasattr(model, field)]
    if not clauses:
        return stmt
    return stmt.where(or_(*clauses))


def filters_echo(pagination: PaginationParams, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build the filters block echoed in the paginated response."""
    base: dict[str, Any] = {
        "search": pagination.search,
        "sort_by": pagination.sort_by,
        "sort_order": pagination.sort_order,
    }
    if extra:
        base.update({k: v for k, v in extra.items() if v is not None})
    return base
