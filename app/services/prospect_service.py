from math import ceil

from sqlalchemy.orm import Session

from app.core.id_generator import generate_id

from app.db.models.prospect import Prospect
from app.db.models.payment import Payment

from app.repositories.prospect_repository import ProspectRepository

from app.schemas.prospect import (
    ProspectCreate,
    ProspectUpdate,
)


class ProspectService:

    @staticmethod
    def create(
        db: Session,
        payload: ProspectCreate,
    ) -> Prospect:

        # Email already exists
        if payload.email:

            existing = ProspectRepository.get_by_email(
                db,
                payload.email,
            )

            if existing:
                raise ValueError(
                    "Email already exists."
                )

        prospect = Prospect(

            prospect_id=generate_id(
                db,
                Prospect,
                "prospect_id",
                "PRO",
            ),

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
        )

        # Inline Payments

        for payment in payload.payments:

            prospect.payments.append(

                Payment(

                    payment_id=generate_id(
                        db,
                        Payment,
                        "payment_id",
                        "PAY",
                    ),

                    amount=payment.amount,

                    payment_type=payment.payment_type,

                    payment_date=payment.payment_date,

                    notes=payment.notes,

                    receipt_url=payment.receipt_url,
                )

            )

        return ProspectRepository.create(
            db,
            prospect,
        )

    @staticmethod
    def list(
        db: Session,
        page: int,
        page_size: int,
        search: str | None,
        stage: str | None,
    ):

        items, total = ProspectRepository.list(
            db,
            page,
            page_size,
            search,
            stage,
        )

        return {

            "items": items,

            "total": total,

            "page": page,

            "page_size": page_size,

            "total_pages": ceil(
                total / page_size
            ) if total else 1,
        }

    @staticmethod
    def get(
        db: Session,
        prospect_id: int,
    ):

        prospect = ProspectRepository.get_by_id(
            db,
            prospect_id,
        )

        if not prospect:
            raise ValueError(
                "Prospect not found."
            )

        return prospect

    @staticmethod
    def update(
        db: Session,
        prospect_id: int,
        payload: ProspectUpdate,
    ):

        prospect = ProspectRepository.get_by_id(
            db,
            prospect_id,
        )

        if not prospect:
            raise ValueError(
                "Prospect not found."
            )

        data = payload.model_dump(
            exclude_unset=True
        )

        for key, value in data.items():

            setattr(
                prospect,
                key,
                value,
            )

        return ProspectRepository.update(
            db,
            prospect,
        )

    @staticmethod
    def delete(
        db: Session,
        prospect_id: int,
    ):

        prospect = ProspectRepository.get_by_id(
            db,
            prospect_id,
        )

        if not prospect:
            raise ValueError(
                "Prospect not found."
            )

        ProspectRepository.delete(
            db,
            prospect,
        )

    @staticmethod
    def change_stage(
        db: Session,
        prospect_id: int,
        stage,
    ):

        prospect = ProspectRepository.get_by_id(
            db,
            prospect_id,
        )

        if not prospect:
            raise ValueError(
                "Prospect not found."
            )

        prospect.stage = stage

        return ProspectRepository.update(
            db,
            prospect,
        )

    @staticmethod
    def update_exam(
        db: Session,
        prospect_id: int,
        attended: bool,
        certified: bool,
    ):

        prospect = ProspectRepository.get_by_id(
            db,
            prospect_id,
        )

        if not prospect:
            raise ValueError(
                "Prospect not found."
            )

        prospect.exam_attended = attended

        prospect.exam_certified = certified

        return ProspectRepository.update(
            db,
            prospect,
        )