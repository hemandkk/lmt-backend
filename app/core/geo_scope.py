"""Filter helpers for state/branch (assignee geography)."""

from __future__ import annotations

from typing import Optional, Tuple

from sqlalchemy import false
from sqlalchemy.orm import Query

from app.db.models.prospect import Prospect
from app.db.models.user import User

# Non-admin users without state/branch get this sentinel so filters match nothing.
_EMPTY_GEO_ID = -1


def resolve_geo_scope(user) -> Tuple[Optional[int], Optional[int]]:
    """
    Admin: (None, None) — no geo restriction.
    Non-admin: (user.state_id, user.branch_id).
    Non-admin missing state or branch: (-1, -1) so queries return empty.
    """
    from app.core.roles import is_admin

    if is_admin(user):
        return None, None

    state_id = getattr(user, "state_id", None)
    branch_id = getattr(user, "branch_id", None)
    if state_id is None or branch_id is None:
        return _EMPTY_GEO_ID, _EMPTY_GEO_ID
    return int(state_id), int(branch_id)


def merge_geo_query_params(
    user,
    requested_state_id: Optional[int] = None,
    requested_branch_id: Optional[int] = None,
) -> Tuple[Optional[int], Optional[int]]:
    """
    Admin may use client stateId/branchId filters.
    Non-admin is always forced to their own state/branch (client params ignored).
    """
    from app.core.roles import is_admin

    if is_admin(user):
        return requested_state_id, requested_branch_id
    return resolve_geo_scope(user)


def assignee_in_geo_scope(prospect, user) -> bool:
    """Whether the lead's assignee falls within the viewer's geo scope."""
    from app.core.roles import is_admin

    if is_admin(user):
        return True

    state_id, branch_id = resolve_geo_scope(user)
    if state_id == _EMPTY_GEO_ID:
        return False

    assignee = getattr(prospect, "assigned_to", None)
    if assignee is None:
        return False
    if state_id is not None and getattr(assignee, "state_id", None) != state_id:
        return False
    if branch_id is not None and getattr(assignee, "branch_id", None) != branch_id:
        return False
    return True


def apply_user_geo_filter(
    query: Query,
    *,
    state_id: Optional[int] = None,
    branch_id: Optional[int] = None,
) -> Query:
    """Filter a User query by state/branch."""
    if state_id == _EMPTY_GEO_ID or branch_id == _EMPTY_GEO_ID:
        return query.filter(false())
    if state_id is not None:
        query = query.filter(User.state_id == state_id)
    if branch_id is not None:
        query = query.filter(User.branch_id == branch_id)
    return query


def apply_prospect_assignee_geo(
    query: Query,
    *,
    state_id: Optional[int] = None,
    branch_id: Optional[int] = None,
    user_already_joined: bool = False,
) -> Query:
    """
    Constrain prospects to those whose assignee belongs to state/branch.
    Joins User on assigned_to_id when needed.
    """
    if state_id == _EMPTY_GEO_ID or branch_id == _EMPTY_GEO_ID:
        return query.filter(false())
    if state_id is None and branch_id is None:
        return query
    if not user_already_joined:
        query = query.join(User, User.id == Prospect.assigned_to_id)
    return apply_user_geo_filter(query, state_id=state_id, branch_id=branch_id)
