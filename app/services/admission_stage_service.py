"""Admission funnel stage helpers (separate from CRM ProspectStage)."""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any, Optional

from app.db.models.payment import PaymentStatus
from app.db.models.prospect import AdmissionStage, Prospect

ADMISSION_STAGE_ORDER = [
    AdmissionStage.registered,
    AdmissionStage.fifty_percent_paid,
    AdmissionStage.exam_attended,
    AdmissionStage.waiting_for_100_percent_payment,
    AdmissionStage.certificate_waiting,
    AdmissionStage.waiting_result,
    AdmissionStage.result_announced,
]

_ALIASES = {
    "registered": AdmissionStage.registered,
    "fifty_percent_paid": AdmissionStage.fifty_percent_paid,
    "50_percent_paid": AdmissionStage.fifty_percent_paid,
    "50percentpaid": AdmissionStage.fifty_percent_paid,
    "fiftypercentpaid": AdmissionStage.fifty_percent_paid,
    "exam_attended": AdmissionStage.exam_attended,
    "examattended": AdmissionStage.exam_attended,
    "waiting_for_100_percent_payment": (
        AdmissionStage.waiting_for_100_percent_payment
    ),
    "waitingfor100percentpayment": (
        AdmissionStage.waiting_for_100_percent_payment
    ),
    "waiting_for_100_payment": (
        AdmissionStage.waiting_for_100_percent_payment
    ),
    "waitingfor100payment": AdmissionStage.waiting_for_100_percent_payment,
    "certificate_waiting": AdmissionStage.certificate_waiting,
    "certificatewaiting": AdmissionStage.certificate_waiting,
    "waiting_result": AdmissionStage.waiting_result,
    "waitingresult": AdmissionStage.waiting_result,
    "result_announced": AdmissionStage.result_announced,
    "resultannounced": AdmissionStage.result_announced,
}


def parse_admission_stage(value: Any) -> AdmissionStage:
    if isinstance(value, AdmissionStage):
        return value
    if value is None:
        raise ValueError("Invalid admission stage: null")

    raw = str(value).strip()
    snake = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", raw).lower()
    snake = snake.replace("-", "_").replace("%", "_percent_")
    compact = re.sub(r"[^a-z0-9]", "", snake)

    if snake in _ALIASES:
        return _ALIASES[snake]
    if compact in _ALIASES:
        return _ALIASES[compact]

    # Tolerate extra spaces in labels like "50 % paid"
    spaced = re.sub(r"\s+", " ", raw.lower()).strip()
    label_map = {
        "registered": AdmissionStage.registered,
        "50 % paid": AdmissionStage.fifty_percent_paid,
        "50% paid": AdmissionStage.fifty_percent_paid,
        "exam attended": AdmissionStage.exam_attended,
        "waiting for 100% payment": (
            AdmissionStage.waiting_for_100_percent_payment
        ),
        "waiting for 100 % payment": (
            AdmissionStage.waiting_for_100_percent_payment
        ),
        "certificate waiting": AdmissionStage.certificate_waiting,
        "waiting result": AdmissionStage.waiting_result,
        "result announced": AdmissionStage.result_announced,
    }
    if spaced in label_map:
        return label_map[spaced]

    raise ValueError(f"Invalid admission stage: {value}")


def _stage_index(stage: Optional[AdmissionStage]) -> int:
    if stage is None:
        return 0
    try:
        return ADMISSION_STAGE_ORDER.index(stage)
    except ValueError:
        return 0


def _advance_to(prospect: Prospect, target: AdmissionStage) -> bool:
    current = prospect.admission_stage or AdmissionStage.registered
    if isinstance(current, str):
        try:
            current = AdmissionStage(current)
        except ValueError:
            current = AdmissionStage.registered
    if _stage_index(target) <= _stage_index(current):
        return False
    prospect.admission_stage = target
    return True


def completed_paid_total(prospect: Prospect) -> Decimal:
    total = Decimal("0")
    for pay in prospect.payments or []:
        status = (
            pay.payment_status.value
            if hasattr(pay.payment_status, "value")
            else str(pay.payment_status or "")
        )
        if status == PaymentStatus.completed.value:
            total += Decimal(str(pay.amount or 0))
    return total


def paid_ratio(prospect: Prospect) -> Decimal:
    estimated = Decimal(str(prospect.estimated_deal_value or 0))
    paid = completed_paid_total(prospect)
    if estimated <= 0:
        return Decimal("1") if paid > 0 else Decimal("0")
    return paid / estimated


def apply_admission_stage_autos(prospect: Prospect) -> bool:
    """
    Auto-advance admission stage (never moves backwards):
    - >= 50% fee paid → fifty_percent_paid
    - examAttended true → exam_attended
    """
    changed = False
    if paid_ratio(prospect) >= Decimal("0.5"):
        changed = _advance_to(prospect, AdmissionStage.fifty_percent_paid) or changed
    if prospect.exam_attended:
        changed = _advance_to(prospect, AdmissionStage.exam_attended) or changed
    return changed
