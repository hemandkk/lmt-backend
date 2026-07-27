"""Filter helpers for state/branch (assignee geography)."""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Query

from app.db.models.prospect import Prospect
from app.db.models.user import User


def apply_user_geo_filter(
    query: Query,
    *,
    state_id: Optional[int] = None,
    branch_id: Optional[int] = None,
) -> Query:
    """Filter a User query by state/branch."""
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
    if state_id is None and branch_id is None:
        return query
    if not user_already_joined:
        query = query.join(User, User.id == Prospect.assigned_to_id)
    return apply_user_geo_filter(query, state_id=state_id, branch_id=branch_id)
