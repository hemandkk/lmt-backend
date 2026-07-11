from math import ceil
from typing import Optional

from sqlalchemy.orm import Session

from app.core.id_generator import generate_id
from app.db.models.payment import Payment, PaymentMethod, PaymentStatus
from app.db.models.prospect import Prospect, ProspectStage
from app.repositories.prospect_repository import ProspectRepository
from app.schemas.prospect import ProspectCreate, ProspectUpdate
from app.services.notification_service import ActivityLogService, NotificationService


class ProspectService:

    @staticmethod
    def create(
        db: Session,
        payload: ProspectCreate,
        actor_id: Optional[int] = None,
    ) -> Prospect:

        if payload.email:
            existing = ProspectRepository.get_by_email(db, payload.email)
            if existing:
                raise ValueError("Email already exists.")

        prospect = Prospect(
            prospect_id=generate_id(db, Prospect, "prospect_id", "PRO"),
            name=payload.name,
            password=payload.password,
            email=payload.email,
            phone=payload.phone,
            father_name=payload.father_name,
            mother_name=payload.mother_name,
            dob=payload.dob,
            course_id=payload.course_id,
            specialization=payload.specialization,
            address=payload.address,
            delivery_address=payload.delivery_address,
            delivery_date=payload.delivery_date,
            estimated_deal_value=payload.estimated_deal_value,
            notes=payload.notes,
            assigned_to_id=payload.assigned_to_id,
            source=payload.source,
            follow_up_date=payload.follow_up_date,
        )

        for payment in payload.payments:
            payment_data = {
                "payment_id": generate_id(db, Payment, "payment_id", "PAY"),
                "amount": payment.amount,
                "payment_type": payment.payment_type,
                "payment_date": payment.payment_date,
                "notes": payment.notes,
                "receipt_url": payment.receipt_url,
                "payment_method": PaymentMethod.cash,
                "payment_status": PaymentStatus.completed,
            }
            prospect.payments.append(Payment(**payment_data))

        created = ProspectRepository.create(db, prospect)

        ActivityLogService.log(
            db,
            action="lead_created",
            entity_type="prospect",
            entity_id=created.id,
            description=f"Lead {created.prospect_id} ({created.name}) created",
            user_id=actor_id,
            prospect_id=created.id,
        )

        if created.assigned_to_id:
            NotificationService.notify_lead_assigned(
                db, created, actor_id=actor_id
            )

        return created

    @staticmethod
    def list(
        db: Session,
        page: int,
        page_size: int,
        search: str | None,
        stage: str | None,
    ):
        items, total = ProspectRepository.list(
            db, page, page_size, search, stage
        )
        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": ceil(total / page_size) if total else 1,
        }

    @staticmethod
    def get(db: Session, prospect_id: int):
        prospect = ProspectRepository.get_by_id(db, prospect_id)
        if not prospect:
            raise ValueError("Prospect not found.")
        return prospect

    @staticmethod
    def update(
        db: Session,
        prospect_id: int,
        payload: ProspectUpdate,
        actor_id: Optional[int] = None,
    ):
        prospect = ProspectRepository.get_by_id(db, prospect_id)
        if not prospect:
            raise ValueError("Prospect not found.")

        old_assigned = prospect.assigned_to_id
        old_stage = (
            prospect.stage.value
            if hasattr(prospect.stage, "value")
            else str(prospect.stage)
        )

        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(prospect, key, value)

        updated = ProspectRepository.update(db, prospect)

        ActivityLogService.log(
            db,
            action="lead_updated",
            entity_type="prospect",
            entity_id=updated.id,
            description=f"Lead {updated.prospect_id} updated",
            user_id=actor_id,
            prospect_id=updated.id,
        )

        if (
            "assigned_to_id" in data
            and updated.assigned_to_id
            and updated.assigned_to_id != old_assigned
        ):
            NotificationService.notify_lead_assigned(
                db, updated, actor_id=actor_id
            )

        if "stage" in data:
            new_stage = (
                updated.stage.value
                if hasattr(updated.stage, "value")
                else str(updated.stage)
            )
            if new_stage != old_stage:
                NotificationService.notify_stage_changed(
                    db,
                    updated,
                    old_stage=old_stage,
                    new_stage=new_stage,
                    actor_id=actor_id,
                )

        return updated

    @staticmethod
    def delete(db: Session, prospect_id: int, actor_id: Optional[int] = None):
        prospect = ProspectRepository.get_by_id(db, prospect_id)
        if not prospect:
            raise ValueError("Prospect not found.")

        ActivityLogService.log(
            db,
            action="lead_deleted",
            entity_type="prospect",
            entity_id=prospect.id,
            description=f"Lead {prospect.prospect_id} deleted",
            user_id=actor_id,
            prospect_id=prospect.id,
        )

        ProspectRepository.delete(db, prospect)

    @staticmethod
    def change_stage(
        db: Session,
        prospect_id: int,
        stage,
        actor_id: Optional[int] = None,
    ):
        prospect = ProspectRepository.get_by_id(db, prospect_id)
        if not prospect:
            raise ValueError("Prospect not found.")

        if isinstance(stage, str):
            try:
                stage = ProspectStage(stage)
            except ValueError as exc:
                raise ValueError(f"Invalid stage: {stage}") from exc

        old_stage = (
            prospect.stage.value
            if hasattr(prospect.stage, "value")
            else str(prospect.stage)
        )
        prospect.stage = stage
        updated = ProspectRepository.update(db, prospect)

        new_stage = (
            updated.stage.value
            if hasattr(updated.stage, "value")
            else str(updated.stage)
        )
        if new_stage != old_stage:
            NotificationService.notify_stage_changed(
                db,
                updated,
                old_stage=old_stage,
                new_stage=new_stage,
                actor_id=actor_id,
            )

        return updated
    @staticmethod
    def update_exam(
        db: Session,
        prospect_id: int,
        attended: bool,
        certified: bool,
    ):
        prospect = ProspectRepository.get_by_id(db, prospect_id)
        if not prospect:
            raise ValueError("Prospect not found.")

        prospect.exam_attended = attended
        prospect.exam_certified = certified
        return ProspectRepository.update(db, prospect)
