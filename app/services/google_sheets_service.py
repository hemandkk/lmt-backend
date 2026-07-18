from __future__ import annotations

import json
import logging
import time
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models.payment import PaymentStatus
from app.db.models.prospect import Prospect
from app.db.models.prospect_document import DocumentType
from app.services.lead_sheet_fields import (
    EXTRA_SYNC_HEADERS,
    build_lead_sync_fields,
    extra_sync_values,
)
from app.services.notification_service import ActivityLogService

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# Column B = Lead ID (used to find/update existing rows)
LEAD_ID_COLUMN_INDEX = 1  # 0-based within the row values

SHEET_HEADERS = [
    "Date",
    "Lead ID",
    "Name",
    "Email",
    "Phone Number",
    "Father name",
    "Mother name",
    "Course name",
    "Specialization",
    "Address",
    "Estimated Deal Value",
    "Delivery Address",
    "Delivery Date",
    "Notes",
    "Aadhaar",
    "Passport",
    "Photo",
    "SSLC",
    "Plus Two",
    "Degree",
    "User Agreement",
    "Assigned Employee",
    "Total Paid",
    "Last Payment Amount",
    "Last Payment Date",
    "Last Payment Type",
    "Sync Status",
    *EXTRA_SYNC_HEADERS,
]


def _column_letter(n: int) -> str:
    """1-based column index → Excel letter(s)."""
    result = ""
    while n > 0:
        n, rem = divmod(n - 1, 26)
        result = chr(65 + rem) + result
    return result


LAST_COLUMN_LETTER = _column_letter(len(SHEET_HEADERS))

DOC_COLUMN_MAP = {
    DocumentType.aadhaar: "Aadhaar",
    DocumentType.passport: "Passport",
    DocumentType.photo: "Photo",
    DocumentType.sslc: "SSLC",
    DocumentType.plus_two: "Plus Two",
    DocumentType.degree: "Degree",
    DocumentType.agreement: "User Agreement",
}


class GoogleSheetsSyncError(Exception):
    """Raised when Google Sheets sync fails after retries."""


def _import_google():
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        from googleapiclient.errors import HttpError
    except ImportError as ex:
        raise GoogleSheetsSyncError(
            "Google Sheets libraries are not installed. "
            "Run: pip install google-api-python-client google-auth google-auth-httplib2"
        ) from ex
    return service_account, build, HttpError


class GoogleSheetsService:
    """Upsert leads to Google Sheets with retries and sync logging."""

    @staticmethod
    def is_configured() -> bool:
        if not settings.GOOGLE_SHEETS_ENABLED:
            return False
        if not settings.GOOGLE_SHEETS_SPREADSHEET_ID:
            return False
        return bool(
            settings.GOOGLE_SERVICE_ACCOUNT_FILE
            or settings.GOOGLE_SERVICE_ACCOUNT_JSON
        )

    @staticmethod
    def _load_credentials():
        service_account, _, _ = _import_google()
        if settings.GOOGLE_SERVICE_ACCOUNT_JSON:
            info = json.loads(settings.GOOGLE_SERVICE_ACCOUNT_JSON)
            return service_account.Credentials.from_service_account_info(
                info, scopes=SCOPES
            )
        if settings.GOOGLE_SERVICE_ACCOUNT_FILE:
            return service_account.Credentials.from_service_account_file(
                settings.GOOGLE_SERVICE_ACCOUNT_FILE,
                scopes=SCOPES,
            )
        raise GoogleSheetsSyncError(
            "Google service account credentials are not configured."
        )

    @staticmethod
    def _sheets_client():
        _, build, _ = _import_google()
        credentials = GoogleSheetsService._load_credentials()
        return build(
            "sheets",
            "v4",
            credentials=credentials,
            cache_discovery=False,
        )

    @staticmethod
    def _worksheet_range(cell_range: str = f"A:{LAST_COLUMN_LETTER}") -> str:
        sheet = settings.GOOGLE_SHEETS_WORKSHEET_NAME
        safe = f"'{sheet}'" if any(c in sheet for c in " '!") else sheet
        return f"{safe}!{cell_range}"

    @staticmethod
    def _format_value(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, datetime):
            return value.date().isoformat()
        if isinstance(value, date):
            return value.isoformat()
        if hasattr(value, "value"):
            return str(value.value)
        return str(value)

    @staticmethod
    def _absolute_url(path: Optional[str]) -> str:
        if not path:
            return ""
        if path.startswith("http://") or path.startswith("https://"):
            return path
        base = settings.APP_BASE_URL.rstrip("/")
        if not path.startswith("/"):
            path = f"/{path}"
        return f"{base}{path}"

    @staticmethod
    def _document_urls(prospect: Prospect) -> dict[str, str]:
        urls = {header: "" for header in DOC_COLUMN_MAP.values()}
        for doc in prospect.documents or []:
            doc_type = doc.document_type
            if isinstance(doc_type, str):
                try:
                    doc_type = DocumentType(doc_type)
                except ValueError:
                    continue
            header = DOC_COLUMN_MAP.get(doc_type)
            if header:
                urls[header] = GoogleSheetsService._absolute_url(doc.file_url)
        return urls

    @staticmethod
    def _payment_summary(prospect: Prospect) -> dict[str, str]:
        completed = []
        for payment in prospect.payments or []:
            status = payment.payment_status
            if status is None:
                completed.append(payment)
                continue
            value = status.value if hasattr(status, "value") else str(status)
            if value == PaymentStatus.completed.value:
                completed.append(payment)

        total = sum((Decimal(str(p.amount or 0)) for p in completed), Decimal("0"))

        def _sort_key(payment):
            return (
                payment.payment_date or date.min,
                getattr(payment, "id", 0) or 0,
            )

        completed.sort(key=_sort_key, reverse=True)
        last = completed[0] if completed else None
        return {
            "total_paid": GoogleSheetsService._format_value(total),
            "last_amount": (
                GoogleSheetsService._format_value(last.amount) if last else ""
            ),
            "last_date": (
                GoogleSheetsService._format_value(last.payment_date) if last else ""
            ),
            "last_type": (
                GoogleSheetsService._format_value(last.payment_type) if last else ""
            ),
        }

    @staticmethod
    def build_row(prospect: Prospect, db: Session | None = None) -> list[str]:
        docs = GoogleSheetsService._document_urls(prospect)
        payments = GoogleSheetsService._payment_summary(prospect)
        course_name = ""
        if getattr(prospect, "course", None) is not None:
            course_name = prospect.course.name or ""
        assignee = ""
        if getattr(prospect, "assigned_to", None) is not None:
            assignee = (
                prospect.assigned_to.name
                or prospect.assigned_to.email
                or ""
            )

        created = getattr(prospect, "created_at", None) or datetime.utcnow()
        extra = build_lead_sync_fields(prospect, db=db)

        return [
            GoogleSheetsService._format_value(created),
            GoogleSheetsService._format_value(prospect.prospect_id),
            GoogleSheetsService._format_value(prospect.name),
            GoogleSheetsService._format_value(prospect.email),
            GoogleSheetsService._format_value(prospect.phone),
            GoogleSheetsService._format_value(prospect.father_name),
            GoogleSheetsService._format_value(prospect.mother_name),
            course_name,
            GoogleSheetsService._format_value(prospect.specialization),
            GoogleSheetsService._format_value(prospect.address),
            GoogleSheetsService._format_value(prospect.estimated_deal_value),
            GoogleSheetsService._format_value(prospect.delivery_address),
            GoogleSheetsService._format_value(prospect.delivery_date),
            GoogleSheetsService._format_value(prospect.notes),
            docs["Aadhaar"],
            docs["Passport"],
            docs["Photo"],
            docs["SSLC"],
            docs["Plus Two"],
            docs["Degree"],
            docs["User Agreement"],
            assignee,
            payments["total_paid"],
            payments["last_amount"],
            payments["last_date"],
            payments["last_type"],
            "synced",
            *extra_sync_values(extra),
        ]

    @staticmethod
    def _ensure_header_row(service) -> None:
        """Write/refresh header row so newly added columns are always present."""
        spreadsheet_id = settings.GOOGLE_SHEETS_SPREADSHEET_ID
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=GoogleSheetsService._worksheet_range("A1"),
            valueInputOption="USER_ENTERED",
            body={"values": [SHEET_HEADERS]},
        ).execute()

    @staticmethod
    def _find_row_number(service, lead_id: str) -> Optional[int]:
        """Return 1-based sheet row number for Lead ID, or None."""
        spreadsheet_id = settings.GOOGLE_SHEETS_SPREADSHEET_ID
        result = (
            service.spreadsheets()
            .values()
            .get(
                spreadsheetId=spreadsheet_id,
                range=GoogleSheetsService._worksheet_range("B:B"),
            )
            .execute()
        )
        values = result.get("values") or []
        target = str(lead_id).strip()
        for index, row in enumerate(values, start=1):
            if not row:
                continue
            if str(row[0]).strip() == target:
                return index
        return None

    @staticmethod
    def _append_row(service, row: list[str]) -> str:
        spreadsheet_id = settings.GOOGLE_SHEETS_SPREADSHEET_ID
        GoogleSheetsService._ensure_header_row(service)
        response = (
            service.spreadsheets()
            .values()
            .append(
                spreadsheetId=spreadsheet_id,
                range=GoogleSheetsService._worksheet_range(
                    f"A:{LAST_COLUMN_LETTER}"
                ),
                valueInputOption="USER_ENTERED",
                insertDataOption="INSERT_ROWS",
                body={"values": [row]},
            )
            .execute()
        )
        updates = response.get("updates") or {}
        return updates.get("updatedRange") or ""

    @staticmethod
    def _update_row(service, row_number: int, row: list[str]) -> str:
        spreadsheet_id = settings.GOOGLE_SHEETS_SPREADSHEET_ID
        cell_range = f"A{row_number}:{LAST_COLUMN_LETTER}{row_number}"
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=GoogleSheetsService._worksheet_range(cell_range),
            valueInputOption="USER_ENTERED",
            body={"values": [row]},
        ).execute()
        return GoogleSheetsService._worksheet_range(cell_range)

    @staticmethod
    def upsert_lead_row(prospect: Prospect, db: Session | None = None) -> str:
        """
        Create or update the sheet row for this lead (matched by Lead ID).
        Retries transient failures with exponential backoff.
        """
        if not GoogleSheetsService.is_configured():
            raise GoogleSheetsSyncError(
                "Google Sheets integration is disabled or incomplete."
            )

        _, _, HttpError = _import_google()
        row = GoogleSheetsService.build_row(prospect, db=db)
        lead_id = str(prospect.prospect_id)
        attempts = max(1, settings.GOOGLE_SHEETS_MAX_RETRIES)
        backoff = settings.GOOGLE_SHEETS_RETRY_BACKOFF_SECONDS
        last_error: Exception | None = None

        for attempt in range(1, attempts + 1):
            try:
                service = GoogleSheetsService._sheets_client()
                GoogleSheetsService._ensure_header_row(service)
                existing_row = GoogleSheetsService._find_row_number(
                    service, lead_id
                )
                if existing_row:
                    return GoogleSheetsService._update_row(
                        service, existing_row, row
                    )
                return GoogleSheetsService._append_row(service, row)
            except HttpError as ex:
                last_error = ex
                status = getattr(ex.resp, "status", None)
                retryable = status in {408, 429, 500, 502, 503, 504}
                logger.warning(
                    "Google Sheets upsert failed (attempt %s/%s, status=%s): %s",
                    attempt,
                    attempts,
                    status,
                    ex,
                )
                if not retryable or attempt >= attempts:
                    break
                time.sleep(backoff * attempt)
            except Exception as ex:
                last_error = ex
                logger.warning(
                    "Google Sheets upsert failed (attempt %s/%s): %s",
                    attempt,
                    attempts,
                    ex,
                )
                if attempt >= attempts:
                    break
                time.sleep(backoff * attempt)

        raise GoogleSheetsSyncError(
            f"Failed to sync lead to Google Sheets after {attempts} attempts: "
            f"{last_error}"
        )

    # Backwards-compatible alias
    @staticmethod
    def append_lead_row(prospect: Prospect) -> str:
        return GoogleSheetsService.upsert_lead_row(prospect)

    @staticmethod
    def sync_prospect(
        db: Session,
        prospect: Prospect,
        actor_id: Optional[int] = None,
    ) -> Prospect:
        """
        Upsert prospect to Google Sheets and persist sync status.
        Never raises — failures are logged and stored on the prospect.
        """
        if not GoogleSheetsService.is_configured():
            logger.info(
                "Skipping Google Sheets sync for %s (not configured).",
                prospect.prospect_id,
            )
            ActivityLogService.log(
                db,
                action="sheets_sync_skipped",
                entity_type="prospect",
                entity_id=prospect.id,
                description=(
                    f"Google Sheets sync skipped for {prospect.prospect_id} "
                    "(disabled or missing credentials)."
                ),
                user_id=actor_id,
                prospect_id=prospect.id,
            )
            return prospect

        try:
            updated_range = GoogleSheetsService.upsert_lead_row(prospect, db=db)
            prospect.sheets_synced = True
            prospect.sheets_row_id = (
                updated_range[:50] if updated_range else None
            )
            db.add(prospect)
            db.commit()
            db.refresh(prospect)

            ActivityLogService.log(
                db,
                action="sheets_sync_success",
                entity_type="prospect",
                entity_id=prospect.id,
                description=(
                    f"Lead {prospect.prospect_id} synced to Google Sheets "
                    f"({updated_range or 'ok'})."
                ),
                user_id=actor_id,
                prospect_id=prospect.id,
                meta_data=json.dumps({"updatedRange": updated_range}),
            )
            logger.info(
                "Synced lead %s to Google Sheets (%s).",
                prospect.prospect_id,
                updated_range,
            )
        except Exception as ex:
            try:
                db.rollback()
            except Exception:
                pass

            fresh = (
                db.query(Prospect)
                .filter(Prospect.id == prospect.id)
                .first()
            )
            if fresh:
                fresh.sheets_synced = False
                db.add(fresh)
                db.commit()
                db.refresh(fresh)
                prospect = fresh

            ActivityLogService.log(
                db,
                action="sheets_sync_failed",
                entity_type="prospect",
                entity_id=prospect.id,
                description=(
                    f"Lead {prospect.prospect_id} Google Sheets sync failed: {ex}"
                ),
                user_id=actor_id,
                prospect_id=prospect.id,
                meta_data=json.dumps({"error": str(ex)}),
            )
            logger.exception(
                "Google Sheets sync failed for lead %s",
                prospect.prospect_id,
            )

        return prospect

    @staticmethod
    def sync_prospect_by_id(
        db: Session,
        prospect_id: int,
        actor_id: Optional[int] = None,
    ) -> Optional[Prospect]:
        """Reload prospect with relations, then upsert to Sheets."""
        from app.repositories.prospect_repository import ProspectRepository

        prospect = ProspectRepository.get_by_id(db, prospect_id)
        if not prospect:
            return None
        return GoogleSheetsService.sync_prospect(
            db, prospect, actor_id=actor_id
        )
