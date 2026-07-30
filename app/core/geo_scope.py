"""Filter helpers for state/branch (assignee geography)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Sequence, Tuple

from sqlalchemy import false, func
from sqlalchemy.orm import Query, aliased

from app.db.models.prospect import Prospect
from app.db.models.user import User

# Sales users without required geo get this sentinel so filters match nothing.
_EMPTY_GEO_ID = -1


@dataclass(frozen=True)
class GeoFilter:
    state_id: Optional[int] = None
    branch_id: Optional[int] = None
    branch_ids: Optional[Tuple[int, ...]] = None

    @property
    def is_empty(self) -> bool:
        return self.state_id == _EMPTY_GEO_ID

    def normalized_branch_ids(self) -> Optional[list[int]]:
        if self.branch_ids:
            return list(self.branch_ids)
        if self.branch_id is not None:
            return [int(self.branch_id)]
        return None


def parse_branch_ids(raw: Optional[str]) -> Optional[list[int]]:
    """Parse CSV branchIds query param, e.g. '1,2,3'."""
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    ids: list[int] = []
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.append(int(part))
        except ValueError as exc:
            raise ValueError(f"Invalid branchIds value: {part!r}") from exc
    return ids or None


def sales_head_assigned_branch_ids(user) -> list[int]:
    """Branch IDs a sales_head may see (M2M, fallback to primary branch_id)."""
    assigned = getattr(user, "assigned_branches", None) or []
    ids = [int(b.id) for b in assigned]
    if not ids:
        primary = getattr(user, "branch_id", None)
        if primary is not None:
            ids = [int(primary)]
    return ids


def resolve_geo_scope(user) -> Tuple[Optional[int], Optional[int]]:
    """
    Resolve forced geo for the logged-in user.

    - Admin: (None, None) — unrestricted.
    - Accountant / processing_team:
        - no state → (None, None) — see all
        - state only → (state_id, None) — all branches in that state
        - state + branch → (state_id, branch_id) — that branch only
    - Sales head:
        - state + assigned branches → (state_id, None) here;
          merge_geo_query_params applies branch IN (assigned).
        - no state / no branches → (-1, -1)
    - Other sales roles:
        - both set → (state_id, branch_id)
        - otherwise → (-1, -1) — empty results
    """
    from app.core.roles import (
        is_admin,
        is_accountant,
        is_processing_team,
        is_sales_head,
    )

    if is_admin(user):
        return None, None

    state_id = getattr(user, "state_id", None)
    branch_id = getattr(user, "branch_id", None)

    if is_accountant(user) or is_processing_team(user):
        if state_id is None:
            return None, None
        return (
            int(state_id),
            int(branch_id) if branch_id is not None else None,
        )

    if is_sales_head(user):
        if state_id is None or not sales_head_assigned_branch_ids(user):
            return _EMPTY_GEO_ID, _EMPTY_GEO_ID
        return int(state_id), None

    if state_id is None or branch_id is None:
        return _EMPTY_GEO_ID, _EMPTY_GEO_ID
    return int(state_id), int(branch_id)


def merge_geo_query_params(
    user,
    requested_state_id: Optional[int] = None,
    requested_branch_id: Optional[int] = None,
    requested_branch_ids: Optional[Sequence[int]] = None,
) -> GeoFilter:
    """
    Merge client geo filters with the viewer's forced scope.

    - Admin: uses client stateId / branchId / branchIds.
    - Sales head: forced to their state + assigned branches; client
      branchId/branchIds may only narrow within that assigned set.
    - Other non-admin: forced to resolve_geo_scope (client params ignored).
    """
    from app.core.roles import is_admin, is_sales_head

    multi = tuple(int(x) for x in requested_branch_ids) if requested_branch_ids else None
    if multi and len(multi) == 1 and requested_branch_id is None:
        requested_branch_id = multi[0]
        multi = None
    if multi and requested_branch_id is not None and requested_branch_id not in multi:
        multi = multi + (int(requested_branch_id),)

    if is_admin(user):
        if multi:
            return GeoFilter(
                state_id=requested_state_id,
                branch_ids=multi,
            )
        return GeoFilter(
            state_id=requested_state_id,
            branch_id=requested_branch_id,
        )

    forced_state, forced_branch = resolve_geo_scope(user)
    if forced_state == _EMPTY_GEO_ID:
        return GeoFilter(state_id=_EMPTY_GEO_ID, branch_id=_EMPTY_GEO_ID)

    if is_sales_head(user):
        allowed = sales_head_assigned_branch_ids(user)
        if not allowed:
            return GeoFilter(state_id=_EMPTY_GEO_ID, branch_id=_EMPTY_GEO_ID)

        if multi:
            narrowed = tuple(b for b in multi if b in allowed)
            if not narrowed:
                return GeoFilter(state_id=_EMPTY_GEO_ID, branch_id=_EMPTY_GEO_ID)
            return GeoFilter(state_id=forced_state, branch_ids=narrowed)

        if requested_branch_id is not None:
            if int(requested_branch_id) not in allowed:
                return GeoFilter(state_id=_EMPTY_GEO_ID, branch_id=_EMPTY_GEO_ID)
            return GeoFilter(
                state_id=forced_state,
                branch_id=int(requested_branch_id),
            )

        return GeoFilter(
            state_id=forced_state,
            branch_ids=tuple(allowed),
        )

    return GeoFilter(state_id=forced_state, branch_id=forced_branch)


def _user_matches_geo(
    target_user: Any,
    state_id: Optional[int],
    branch_id: Optional[int],
    branch_ids: Optional[Sequence[int]] = None,
) -> bool:
    if target_user is None:
        return False
    if state_id is not None and getattr(target_user, "state_id", None) != state_id:
        return False
    ids = list(branch_ids) if branch_ids else None
    if ids:
        return getattr(target_user, "branch_id", None) in ids
    if branch_id is not None and getattr(target_user, "branch_id", None) != branch_id:
        return False
    return True


def assignee_in_geo_scope(prospect, user) -> bool:
    """Whether the lead's assignee falls within the viewer's geo scope."""
    from app.core.roles import is_admin, is_sales_head

    if is_admin(user):
        return True

    if is_sales_head(user):
        geo = merge_geo_query_params(user)
        if geo.is_empty:
            return False
        return _user_matches_geo(
            getattr(prospect, "assigned_to", None),
            geo.state_id,
            geo.branch_id,
            geo.normalized_branch_ids(),
        )

    state_id, branch_id = resolve_geo_scope(user)
    if state_id is None and branch_id is None:
        return True
    if state_id == _EMPTY_GEO_ID:
        return False

    return _user_matches_geo(
        getattr(prospect, "assigned_to", None), state_id, branch_id
    )


def related_user_in_geo_scope(viewer, *candidates: Any) -> bool:
    """Whether preferred related user is in viewer geo."""
    from app.core.roles import is_admin

    if is_admin(viewer):
        return True

    state_id, branch_id = resolve_geo_scope(viewer)
    if state_id is None and branch_id is None:
        return True
    if state_id == _EMPTY_GEO_ID:
        return False

    anchor = next((u for u in candidates if u is not None), None)
    return _user_matches_geo(anchor, state_id, branch_id)


def entity_in_geo_scope(viewer, row, *related_users: Any) -> bool:
    """
    Whether an expense / payment-request is in viewer geo.
    Prefers row.state_id/branch_id; falls back to related users (first non-None).
    """
    from app.core.roles import is_admin

    if is_admin(viewer):
        return True

    state_id, branch_id = resolve_geo_scope(viewer)
    if state_id is None and branch_id is None:
        return True
    if state_id == _EMPTY_GEO_ID:
        return False

    effective_state = getattr(row, "state_id", None)
    effective_branch = getattr(row, "branch_id", None)
    if effective_state is None:
        anchor = next((u for u in related_users if u is not None), None)
        if anchor is None:
            return False
        effective_state = getattr(anchor, "state_id", None)
        effective_branch = getattr(anchor, "branch_id", None)

    if state_id is not None and effective_state != state_id:
        return False
    if branch_id is not None and effective_branch != branch_id:
        return False
    return True


def _normalize_branch_ids(
    branch_id: Optional[int],
    branch_ids: Optional[Sequence[int]],
) -> Optional[list[int]]:
    if branch_ids:
        return [int(x) for x in branch_ids]
    if branch_id is not None:
        return [int(branch_id)]
    return None


def apply_user_geo_filter(
    query: Query,
    *,
    state_id: Optional[int] = None,
    branch_id: Optional[int] = None,
    branch_ids: Optional[Sequence[int]] = None,
    user_model=User,
) -> Query:
    """Filter a User (or aliased User) query by state/branch(es)."""
    if state_id == _EMPTY_GEO_ID:
        return query.filter(false())
    if state_id is not None:
        query = query.filter(user_model.state_id == state_id)
    ids = _normalize_branch_ids(branch_id, branch_ids)
    if ids:
        if len(ids) == 1:
            query = query.filter(user_model.branch_id == ids[0])
        else:
            query = query.filter(user_model.branch_id.in_(ids))
    return query


def apply_related_user_geo(
    query: Query,
    *user_id_columns,
    state_id: Optional[int] = None,
    branch_id: Optional[int] = None,
    branch_ids: Optional[Sequence[int]] = None,
) -> Query:
    """Join related User and filter by geo."""
    if state_id == _EMPTY_GEO_ID:
        return query.filter(false())
    ids = _normalize_branch_ids(branch_id, branch_ids)
    if state_id is None and not ids:
        return query
    if not user_id_columns:
        return query

    geo_user = aliased(User)
    geo_user_id = (
        user_id_columns[0]
        if len(user_id_columns) == 1
        else func.coalesce(*user_id_columns)
    )
    query = query.join(geo_user, geo_user.id == geo_user_id)
    return apply_user_geo_filter(
        query,
        state_id=state_id,
        branch_id=branch_id,
        branch_ids=branch_ids,
        user_model=geo_user,
    )


def apply_entity_geo_filter(
    query: Query,
    *,
    state_col,
    branch_col,
    user_id_columns: Tuple,
    state_id: Optional[int] = None,
    branch_id: Optional[int] = None,
    branch_ids: Optional[Sequence[int]] = None,
) -> Query:
    """
    Filter by COALESCE(stored state/branch, related-user state/branch).
    Outer-joins related user so admin-tagged office rows still match.
    """
    if state_id == _EMPTY_GEO_ID:
        return query.filter(false())
    ids = _normalize_branch_ids(branch_id, branch_ids)
    if state_id is None and not ids:
        return query
    if not user_id_columns:
        return query

    geo_user = aliased(User)
    geo_user_id = (
        user_id_columns[0]
        if len(user_id_columns) == 1
        else func.coalesce(*user_id_columns)
    )
    query = query.outerjoin(geo_user, geo_user.id == geo_user_id)
    if state_id is not None:
        query = query.filter(func.coalesce(state_col, geo_user.state_id) == state_id)
    if ids:
        effective_branch = func.coalesce(branch_col, geo_user.branch_id)
        if len(ids) == 1:
            query = query.filter(effective_branch == ids[0])
        else:
            query = query.filter(effective_branch.in_(ids))
    return query


def resolve_stored_geo(
    db,
    *,
    employee_id: Optional[int] = None,
    state_id: Optional[int] = None,
    branch_id: Optional[int] = None,
    actor=None,
) -> Tuple[Optional[int], Optional[int]]:
    """
    Resolve state/branch to persist on expense / payment-request.

    - Client stateId/branchId wins (validated).
    - Else if employee_id set → store null (list scopes via employee).
    - Else if actor has state → copy actor geo.
    - Else → require stateId (raises ValueError).
    """
    from app.repositories.branch_repository import BranchRepository
    from app.repositories.state_repository import StateRepository

    def _validate(
        sid: Optional[int], bid: Optional[int]
    ) -> Tuple[Optional[int], Optional[int]]:
        if sid is None and bid is None:
            return None, None
        if bid is not None and sid is None:
            branch = BranchRepository.get_by_id(db, bid)
            if not branch:
                raise ValueError("Branch not found.")
            sid = branch.state_id
        if sid is not None:
            state = StateRepository.get_by_id(db, sid)
            if not state:
                raise ValueError("State not found.")
        if bid is not None:
            branch = BranchRepository.get_by_id(db, bid)
            if not branch:
                raise ValueError("Branch not found.")
            if branch.state_id != sid:
                raise ValueError(
                    "Branch does not belong to the selected state."
                )
        return sid, bid

    if state_id is not None or branch_id is not None:
        return _validate(state_id, branch_id)

    if employee_id is not None:
        return None, None

    actor_state = getattr(actor, "state_id", None) if actor else None
    actor_branch = getattr(actor, "branch_id", None) if actor else None
    if actor_state is not None:
        return (
            int(actor_state),
            int(actor_branch) if actor_branch is not None else None,
        )

    raise ValueError(
        "stateId is required when creating without an employee "
        "and the actor has no assigned state."
    )


def apply_prospect_assignee_geo(
    query: Query,
    *,
    state_id: Optional[int] = None,
    branch_id: Optional[int] = None,
    branch_ids: Optional[Sequence[int]] = None,
    user_already_joined: bool = False,
) -> Query:
    """
    Constrain prospects to those whose assignee belongs to state/branch(es).
    Joins User on assigned_to_id when needed.
    """
    if state_id == _EMPTY_GEO_ID:
        return query.filter(false())
    ids = _normalize_branch_ids(branch_id, branch_ids)
    if state_id is None and not ids:
        return query
    if not user_already_joined:
        query = query.join(User, User.id == Prospect.assigned_to_id)
    return apply_user_geo_filter(
        query,
        state_id=state_id,
        branch_id=branch_id,
        branch_ids=branch_ids,
    )
