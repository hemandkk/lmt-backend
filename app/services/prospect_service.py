from math import ceil
from typing import Any, Optional
from uuid import uuid4
import re

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.file_storage import FileStorage
from app.core.id_generator import generate_id, generate_next_code
from app.core.security import hash_password
from app.db.models.payment import (
    Payment,
    PaymentMethod,
    PaymentStatus,
    PaymentVerificationStatus,
)
from app.db.models.prospect import AdmissionStage, Prospect, ProspectStage
from app.db.models.prospect_document import DocumentType, ProspectDocument
from app.db.models.user import User, UserRole
from app.repositories.prospect_repository import ProspectRepository
from app.schemas.prospect import (
    LeadDocumentInput,
    LeadPaymentInput,
    ProspectCreate,
    ProspectUpdate,
)
from app.services.admission_stage_service import (
    apply_admission_stage_autos,
    parse_admission_stage,
)
from app.services.notification_service import ActivityLogService, NotificationService


class ProspectService:

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_assignee(db: Session, assigned_to_id: Optional[int]) -> None:
        """Ensure assignee is an active sales user when provided."""
        if assigned_to_id is None:
            return
        from app.core.roles import SALES_ROLES

        user = (
            db.query(User)
            .filter(
                User.id == assigned_to_id,
                User.role.in_(list(SALES_ROLES)),
                User.is_active.is_(True),
            )
            .first()
        )
        if not user:
            raise ValueError(
                "assignedToId must be an active employee, manager, or sales_head."
            )

    @staticmethod
    def _unique_code(
        db: Session,
        model,
        field: str,
        prefix: str,
        digits: int = 5,
    ) -> str:
        """Code unique against DB rows and pending session objects."""
        code = generate_id(db, model, field, prefix, digits=digits)
        pending = {
            getattr(obj, field)
            for obj in db.new
            if isinstance(obj, model)
        }
        attempts = 0
        while code in pending or (
            db.query(model).filter(getattr(model, field) == code).first()
        ):
            attempts += 1
            code = f"{prefix}{uuid4().hex[:digits].upper()}"
            if attempts > 20:
                break
        return code

    @staticmethod
    def _resolve_prospect_code(
        db: Session,
        requested: Optional[str],
    ) -> str:
        if requested:
            existing = ProspectRepository.get_by_prospect_id(db, requested)
            if existing:
                raise ValueError(f"Prospect ID {requested} already exists.")
            return requested
        return generate_next_code(db, Prospect, "prospect_id", "PRO")

    @staticmethod
    def _build_payment(
        db: Session,
        payment_in: LeadPaymentInput,
        receipt_file: Optional[UploadFile] = None,
        prospect_code: Optional[str] = None,
    ) -> Payment:
        receipt_url = payment_in.receipt_url
        payment_code = ProspectService._unique_code(
            db, Payment, "payment_id", "PAY"
        )

        if receipt_file and receipt_file.filename:
            folder = f"prospects/{prospect_code or 'temp'}/receipts"
            receipt_url, _, _ = FileStorage.save_file(
                upload_file=receipt_file,
                folder=folder,
                filename=payment_code,
            )

        return Payment(
            payment_id=payment_code,
            amount=payment_in.amount,
            payment_type=payment_in.payment_type,
            payment_method=payment_in.payment_method or PaymentMethod.cash,
            payment_status=payment_in.payment_status or PaymentStatus.completed,
            payment_date=payment_in.payment_date,
            notes=payment_in.notes,
            receipt_url=receipt_url,
            transaction_number=payment_in.transaction_number,
            reference_number=payment_in.reference_number,
            verification_status=PaymentVerificationStatus.not_verified,
        )

    @staticmethod
    def _save_document(
        db: Session,
        prospect: Prospect,
        doc_type: DocumentType,
        file: UploadFile,
        remarks: Optional[str] = None,
        existing: Optional[ProspectDocument] = None,
    ) -> ProspectDocument:
        document_code = (
            existing.document_id
            if existing
            else ProspectService._unique_code(
                db, ProspectDocument, "document_id", "DOC"
            )
        )

        if existing and existing.file_url:
            file_url, stored_filename, file_size = FileStorage.replace_file(
                old_file=existing.file_url,
                upload_file=file,
                folder=f"prospects/{prospect.prospect_id}",
                filename=document_code,
            )
            existing.document_type = doc_type
            existing.original_filename = file.filename or existing.original_filename
            existing.stored_filename = stored_filename
            existing.file_url = file_url
            existing.mime_type = file.content_type
            existing.file_size = file_size
            if remarks is not None:
                existing.remarks = remarks
            return existing

        file_url, stored_filename, file_size = FileStorage.save_file(
            upload_file=file,
            folder=f"prospects/{prospect.prospect_id}",
            filename=document_code,
        )

        return ProspectDocument(
            document_id=document_code,
            prospect_id=prospect.id,
            document_type=doc_type,
            original_filename=file.filename or "document",
            stored_filename=stored_filename,
            file_url=file_url,
            mime_type=file.content_type,
            file_size=file_size,
            remarks=remarks,
            verified=False,
        )

    @staticmethod
    def _apply_documents(
        db: Session,
        prospect: Prospect,
        documents_meta: list[LeadDocumentInput],
        document_files: dict[str, UploadFile],
    ) -> None:
        """
        document_files keys: doc type value e.g. "aadhaar", "photo".
        """
        existing_by_type = {
            (
                d.document_type.value
                if hasattr(d.document_type, "value")
                else str(d.document_type)
            ): d
            for d in (prospect.documents or [])
        }

        for meta in documents_meta or []:
            doc_type = meta.doc_type
            key = doc_type.value if hasattr(doc_type, "value") else str(doc_type)
            upload = document_files.get(key)

            if not upload or not upload.filename:
                # Keep existing document referenced by existingUrl / id
                continue

            existing = existing_by_type.get(key)
            saved = ProspectService._save_document(
                db,
                prospect,
                doc_type,
                upload,
                existing=existing,
            )
            if existing is None:
                prospect.documents.append(saved)
                existing_by_type[key] = saved

        # Files sent without metadata entry still upload
        for key, upload in document_files.items():
            if not upload or not upload.filename:
                continue
            if any(
                (m.doc_type.value if hasattr(m.doc_type, "value") else str(m.doc_type))
                == key
                for m in (documents_meta or [])
            ):
                continue
            try:
                doc_type = DocumentType(key)
            except ValueError:
                continue
            existing = existing_by_type.get(key)
            saved = ProspectService._save_document(
                db, prospect, doc_type, upload, existing=existing
            )
            if existing is None:
                prospect.documents.append(saved)

    @staticmethod
    def _sync_payments(
        db: Session,
        prospect: Prospect,
        payments: list[LeadPaymentInput],
        receipt_files: dict[int, UploadFile],
        replace: bool = True,
    ) -> None:
        existing_by_id = {p.id: p for p in (prospect.payments or [])}
        kept_ids: set[int] = set()

        for index, payment_in in enumerate(payments or []):
            receipt = receipt_files.get(index)
            if payment_in.id and payment_in.id in existing_by_id:
                payment = existing_by_id[payment_in.id]
                payment.amount = payment_in.amount
                payment.payment_type = payment_in.payment_type
                payment.payment_date = payment_in.payment_date
                payment.notes = payment_in.notes
                payment.payment_method = (
                    payment_in.payment_method or payment.payment_method
                )
                payment.payment_status = (
                    payment_in.payment_status or payment.payment_status
                )
                payment.transaction_number = payment_in.transaction_number
                payment.reference_number = payment_in.reference_number
                if payment_in.receipt_url is not None and not receipt:
                    payment.receipt_url = payment_in.receipt_url
                if receipt and receipt.filename:
                    url, _, _ = FileStorage.save_file(
                        upload_file=receipt,
                        folder=f"prospects/{prospect.prospect_id}/receipts",
                        filename=payment.payment_id,
                    )
                    payment.receipt_url = url
                kept_ids.add(payment.id)
            else:
                new_payment = ProspectService._build_payment(
                    db,
                    payment_in,
                    receipt_file=receipt,
                    prospect_code=prospect.prospect_id,
                )
                new_payment.prospect_id = prospect.id
                prospect.payments.append(new_payment)

        if replace:
            for payment in list(prospect.payments):
                if payment.id and payment.id not in kept_ids:
                    # Only delete previously persisted rows not in payload
                    if payment.id in existing_by_id:
                        if payment.receipt_url:
                            FileStorage.delete_file(payment.receipt_url)
                        prospect.payments.remove(payment)
                        db.delete(payment)

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    @staticmethod
    def create(
        db: Session,
        payload: ProspectCreate,
        actor_id: Optional[int] = None,
        document_files: Optional[dict[str, UploadFile]] = None,
        receipt_files: Optional[dict[int, UploadFile]] = None,
    ) -> Prospect:
        if payload.email:
            existing = ProspectRepository.get_by_email(db, payload.email)
            if existing:
                raise ValueError("Email already exists.")

        ProspectService._validate_assignee(db, payload.assigned_to_id)

        prospect_code = ProspectService._resolve_prospect_code(
            db, payload.prospect_id
        )

        prospect = Prospect(
            prospect_id=prospect_code,
            name=payload.name,
            password=(
                hash_password(payload.password) if payload.password else None
            ),
            email=payload.email,
            phone=payload.phone,
            father_name=payload.father_name,
            mother_name=payload.mother_name,
            dob=payload.dob,
            course_id=payload.course_id,
            specialization=payload.specialization,
            university=payload.university,
            address=payload.address,
            delivery_address=payload.delivery_address,
            delivery_date=payload.delivery_date,
            estimated_deal_value=payload.estimated_deal_value,
            notes=payload.notes,
            assigned_to_id=payload.assigned_to_id,
            source=payload.source,
            follow_up_date=payload.follow_up_date,
            stage=payload.stage or ProspectStage.new,
            admission_stage=(
                payload.admission_stage or AdmissionStage.registered
            ),
            created_by_id=actor_id,
            updated_by_id=actor_id,
        )

        receipt_files = receipt_files or {}
        for index, payment_in in enumerate(payload.payments or []):
            prospect.payments.append(
                ProspectService._build_payment(
                    db,
                    payment_in,
                    receipt_file=receipt_files.get(index),
                    prospect_code=prospect_code,
                )
            )

        created = ProspectRepository.create(db, prospect)

        # Documents need prospect.id; attach after initial create
        if payload.documents or document_files:
            ProspectService._apply_documents(
                db,
                created,
                payload.documents or [],
                document_files or {},
            )
            created = ProspectRepository.update(db, created)

        # Auto admission stage from create-time payments
        created = ProspectRepository.get_by_id(db, created.id)
        if created and apply_admission_stage_autos(created):
            created = ProspectRepository.update(db, created)

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

        # Reload with relations for Sheets row (course, assignee, documents)
        created = ProspectRepository.get_by_id(db, created.id)

        from app.services.google_sheets_service import GoogleSheetsService

        created = GoogleSheetsService.sync_prospect(
            db, created, actor_id=actor_id
        )

        return ProspectRepository.get_by_id(db, created.id)

    @staticmethod
    def list(
        db: Session,
        page: int,
        page_size: int,
        search: str | None,
        stage: str | None,
        admission_stage: str | None = None,
        admission_stages: list[str] | None = None,
        assigned_to_id: int | None = None,
        course_id: int | None = None,
    ):
        parsed_stages: list[str] | None = None
        if admission_stages:
            parsed_stages = [
                parse_admission_stage(s).value for s in admission_stages
            ]
        elif admission_stage:
            parsed_stages = [parse_admission_stage(admission_stage).value]

        items, total = ProspectRepository.list(
            db,
            page,
            page_size,
            search,
            stage,
            admission_stages=parsed_stages,
            assigned_to_id=assigned_to_id,
            course_id=course_id,
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
        document_files: Optional[dict[str, UploadFile]] = None,
        receipt_files: Optional[dict[int, UploadFile]] = None,
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

        data = payload.model_dump(
            exclude_unset=True,
            exclude={"payments", "documents", "replace_payments"},
        )
        if "assigned_to_id" in data:
            ProspectService._validate_assignee(db, data.get("assigned_to_id"))
        for key, value in data.items():
            if key == "password":
                value = hash_password(value)
            setattr(prospect, key, value)

        if actor_id is not None:
            prospect.updated_by_id = actor_id

        if payload.payments is not None:
            ProspectService._sync_payments(
                db,
                prospect,
                payload.payments,
                receipt_files or {},
                replace=payload.replace_payments,
            )

        if payload.documents is not None or document_files:
            ProspectService._apply_documents(
                db,
                prospect,
                payload.documents or [],
                document_files or {},
            )

        apply_admission_stage_autos(prospect)
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

        return ProspectService._after_change_sync(db, updated.id, actor_id)

    @staticmethod
    def _after_change_sync(
        db: Session,
        prospect_id: int,
        actor_id: Optional[int] = None,
    ):
        from app.services.google_sheets_service import GoogleSheetsService

        GoogleSheetsService.sync_prospect_by_id(
            db, prospect_id, actor_id=actor_id
        )
        return ProspectRepository.get_by_id(db, prospect_id)

    @staticmethod
    def delete(db: Session, prospect_id: int, actor_id: Optional[int] = None):
        prospect = ProspectRepository.get_by_id(db, prospect_id)
        if not prospect:
            raise ValueError("Prospect not found.")

        for document in list(prospect.documents or []):
            FileStorage.delete_file(document.file_url)
        for payment in list(prospect.payments or []):
            if payment.receipt_url:
                FileStorage.delete_file(payment.receipt_url)

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
    def assign(
        db: Session,
        prospect_id: int,
        assigned_to_id: Optional[int],
        actor_id: Optional[int] = None,
    ):
        """Assign or reassign a lead to an employee (or clear with None)."""
        prospect = ProspectRepository.get_by_id(db, prospect_id)
        if not prospect:
            raise ValueError("Prospect not found.")

        ProspectService._validate_assignee(db, assigned_to_id)
        old_assigned = prospect.assigned_to_id
        if old_assigned == assigned_to_id:
            return prospect

        prospect.assigned_to_id = assigned_to_id
        if actor_id is not None:
            prospect.updated_by_id = actor_id
        updated = ProspectRepository.update(db, prospect)

        ActivityLogService.log(
            db,
            action="lead_reassigned" if old_assigned else "lead_assigned",
            entity_type="prospect",
            entity_id=updated.id,
            description=(
                f"Lead {updated.prospect_id} assigned to "
                f"{assigned_to_id if assigned_to_id else 'unassigned'}"
                + (f" (was {old_assigned})" if old_assigned else "")
            ),
            user_id=actor_id,
            prospect_id=updated.id,
            meta_data=None,
        )

        if updated.assigned_to_id:
            NotificationService.notify_lead_assigned(
                db, updated, actor_id=actor_id
            )

        return ProspectService._after_change_sync(db, updated.id, actor_id)

    @staticmethod
    def change_stage(
        db: Session,
        prospect_id: int,
        stage: Any,
        actor_id: Optional[int] = None,
    ):
        prospect = ProspectRepository.get_by_id(db, prospect_id)
        if not prospect:
            raise ValueError("Prospect not found.")

        if isinstance(stage, str):
            snake = re.sub(
                r"([a-z0-9])([A-Z])", r"\1_\2", stage.strip()
            ).lower().replace("-", "_")
            aliases = {"followup": "follow_up"}
            snake = aliases.get(snake, snake)
            try:
                stage = ProspectStage(snake)
            except ValueError as exc:
                raise ValueError(f"Invalid stage: {stage}") from exc

        old_stage = (
            prospect.stage.value
            if hasattr(prospect.stage, "value")
            else str(prospect.stage)
        )
        prospect.stage = stage
        if actor_id is not None:
            prospect.updated_by_id = actor_id
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

        return ProspectService._after_change_sync(db, updated.id, actor_id)

    @staticmethod
    def change_admission_stage(
        db: Session,
        prospect_id: int,
        admission_stage: Any,
        actor_id: Optional[int] = None,
    ):
        prospect = ProspectRepository.get_by_id(db, prospect_id)
        if not prospect:
            raise ValueError("Prospect not found.")

        try:
            stage = parse_admission_stage(admission_stage)
        except ValueError as exc:
            raise ValueError(f"Invalid admission stage: {admission_stage}") from exc

        old_stage = (
            prospect.admission_stage.value
            if hasattr(prospect.admission_stage, "value")
            else str(prospect.admission_stage or "")
        )

        prospect.admission_stage = stage
        if actor_id is not None:
            prospect.updated_by_id = actor_id
        ProspectRepository.update(db, prospect)

        ActivityLogService.log(
            db,
            action="admission_stage_change",
            entity_type="prospect",
            entity_id=prospect.id,
            description=(
                f"Admission stage {old_stage} → {stage.value} "
                f"for {prospect.prospect_id}"
            ),
            user_id=actor_id,
            prospect_id=prospect.id,
            detail={
                "from": old_stage,
                "to": stage.value,
                "prospectId": prospect.prospect_id,
                "prospectName": prospect.name,
            },
        )

        return ProspectService._after_change_sync(db, prospect_id, actor_id)

    @staticmethod
    def refresh_admission_stage(
        db: Session,
        prospect_id: int,
        actor_id: Optional[int] = None,
    ):
        """Re-apply payment/exam auto rules after payment changes."""
        prospect = ProspectRepository.get_by_id(db, prospect_id)
        if not prospect:
            return None
        if apply_admission_stage_autos(prospect):
            if actor_id is not None:
                prospect.updated_by_id = actor_id
            ProspectRepository.update(db, prospect)
        return ProspectRepository.get_by_id(db, prospect_id)

    @staticmethod
    def update_exam(
        db: Session,
        prospect_id: int,
        attended: Optional[bool] = None,
        certified: Optional[bool] = None,
        actor_id: Optional[int] = None,
    ):
        prospect = ProspectRepository.get_by_id(db, prospect_id)
        if not prospect:
            raise ValueError("Prospect not found.")

        if attended is not None:
            prospect.exam_attended = attended
        if certified is not None:
            prospect.exam_certified = certified
        if actor_id is not None:
            prospect.updated_by_id = actor_id
        apply_admission_stage_autos(prospect)
        ProspectRepository.update(db, prospect)
        return ProspectService._after_change_sync(db, prospect_id, actor_id)
