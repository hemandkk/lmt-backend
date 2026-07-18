"""Shared lead field builders for Google Sheets sync and Excel export."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.db.models.activity_log import ActivityLog
from app.db.models.payment import PaymentStatus
from app.db.models.prospect import Prospect


def _user_label(user) -> str:
    if user is None:
        return ""
    return (user.name or user.email or user.employee_id or "").strip()


def _fmt(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, Decimal):
        quantized = value.quantize(Decimal("0.01"))
        if quantized == quantized.to_integral():
            return str(int(quantized))
        return str(quantized)
    if hasattr(value, "value"):
        return str(value.value)
    return str(value)


def build_lead_sync_fields(
    prospect: Prospect,
    db: Optional[Session] = None,
) -> dict[str, str]:
    """
    Extra CRM fields for Sheets / Excel.

    Department / Designation come from the lead owner (assignee).
    Remarks maps to notes.
    """
    owner = getattr(prospect, "assigned_to", None)
    created_by = getattr(prospect, "created_by", None)
    updated_by = getattr(prospect, "updated_by", None)

    estimated = Decimal(str(prospect.estimated_deal_value or 0))
    payment_count = 0
    total_paid = Decimal("0")
    for pay in prospect.payments or []:
        status = (
            pay.payment_status.value
            if hasattr(pay.payment_status, "value")
            else str(pay.payment_status or "")
        )
        if status == PaymentStatus.completed.value:
            payment_count += 1
            total_paid += Decimal(str(pay.amount or 0))

    balance = estimated - total_paid
    if balance < 0:
        balance = Decimal("0")

    stage = (
        prospect.stage.value
        if hasattr(prospect.stage, "value")
        else str(prospect.stage or "")
    )
    follow_up = prospect.follow_up_date
    next_follow_up = _fmt(follow_up) if follow_up else ""

    last_activity = ""
    if db is not None and prospect.id:
        log = (
            db.query(ActivityLog)
            .filter(ActivityLog.prospect_id == prospect.id)
            .order_by(ActivityLog.created_at.desc())
            .first()
        )
        if log:
            when = _fmt(getattr(log, "created_at", None))
            last_activity = f"{log.action}: {log.description}"
            if when:
                last_activity = f"{when} — {last_activity}"
            if not _user_label(updated_by) and log.user_id:
                from app.db.models.user import User

                actor = db.query(User).filter(User.id == log.user_id).first()
                if actor:
                    updated_by = actor

    certified = bool(prospect.exam_certified)
    certificate_status = "Certified" if certified else "Not Certified"

    return {
        "lead_owner": _user_label(owner),
        "follow_up_date": _fmt(follow_up),
        "next_follow_up": next_follow_up,
        "current_lead_stage": stage,
        "last_activity": last_activity,
        "last_updated_by": _user_label(updated_by),
        "university": _fmt(prospect.university),
        "department": _fmt(getattr(owner, "department", None) if owner else None),
        "designation": _fmt(getattr(owner, "designation", None) if owner else None),
        "remarks": _fmt(prospect.notes),
        "created_by": _user_label(created_by),
        "created_at": _fmt(getattr(prospect, "created_at", None)),
        "updated_at": _fmt(getattr(prospect, "updated_at", None)),
        "payment_count": str(payment_count),
        "total_paid": _fmt(total_paid),
        "balance_amount": _fmt(balance),
        "certificate_status": certificate_status,
        "exam_attended": _fmt(bool(prospect.exam_attended)),
        "exam_certified": _fmt(certified),
    }


EXTRA_SYNC_HEADERS = [
    "Lead Owner",
    "Follow-up Date",
    "Next Follow-up",
    "Current Lead Stage",
    "Last Activity",
    "Last Updated By",
    "University",
    "Department",
    "Designation",
    "Remarks",
    "Created By",
    "Created At",
    "Updated At",
    "Payment Count",
    "Total Paid",
    "Balance Amount",
    "Certificate Status",
    "Exam Attended",
    "Exam Certified",
]


def extra_sync_values(fields: dict[str, str]) -> list[str]:
    return [
        fields.get("lead_owner", ""),
        fields.get("follow_up_date", ""),
        fields.get("next_follow_up", ""),
        fields.get("current_lead_stage", ""),
        fields.get("last_activity", ""),
        fields.get("last_updated_by", ""),
        fields.get("university", ""),
        fields.get("department", ""),
        fields.get("designation", ""),
        fields.get("remarks", ""),
        fields.get("created_by", ""),
        fields.get("created_at", ""),
        fields.get("updated_at", ""),
        fields.get("payment_count", ""),
        fields.get("total_paid", ""),
        fields.get("balance_amount", ""),
        fields.get("certificate_status", ""),
        fields.get("exam_attended", ""),
        fields.get("exam_certified", ""),
    ]
