import csv
import io
from datetime import date
from decimal import Decimal
from typing import Any, Optional

from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models.payment import PaymentStatus
from app.db.models.prospect_document import DocumentType
from app.repositories.analytics_repository import AnalyticsRepository
from app.repositories.prospect_repository import ProspectRepository
from app.services.dashboard_service import DashboardService


DOC_TYPE_LABELS = {
    DocumentType.aadhaar: "Aadhaar",
    DocumentType.sslc: "SSLC",
    DocumentType.plus_two: "Plus Two",
    DocumentType.degree: "Degree",
    DocumentType.agreement: "Agreement",
    DocumentType.passport: "Passport",
    DocumentType.photo: "Photo",
    DocumentType.receipt: "Receipt Doc",
    DocumentType.other: "Other Doc",
}


class ExportService:

    @staticmethod
    def _absolute_file_url(path: str | None) -> str:
        if not path:
            return ""
        if path.startswith("http://") or path.startswith("https://"):
            return path
        base = (settings.APP_BASE_URL or "http://localhost:8000").rstrip("/")
        return f"{base}{path if path.startswith('/') else '/' + path}"

    @staticmethod
    def export_prospects_xlsx(
        db: Session,
        *,
        search: str | None = None,
        stage: str | None = None,
        admission_stage: str | None = None,
        admission_stages: list[str] | None = None,
        assigned_to_id: int | None = None,
        course_id: int | None = None,
    ) -> StreamingResponse:
        """
        Full lead export matching list filters.
        Includes create/edit fields (no password) + document & payment file links.
        """
        from app.services.admission_stage_service import parse_admission_stage

        parsed_stages = admission_stages
        if parsed_stages is None and admission_stage:
            parsed_stages = [parse_admission_stage(admission_stage).value]

        prospects = ProspectRepository.list_for_export(
            db,
            search=search,
            stage=stage,
            admission_stages=parsed_stages,
            assigned_to_id=assigned_to_id,
            course_id=course_id,
        )

        from app.db.models.course import Course

        course_names = {
            c.id: (c.name or "").strip()
            for c in db.query(Course.id, Course.name).all()
        }

        doc_types = list(DocumentType)
        headers = [
            "Prospect ID",
            "Name",
            "Email",
            "Phone",
            "DOB",
            "Father Name",
            "Mother Name",
            "Stream Name",
            "Course",
            "University",
            "Address",
            "Delivery Address",
            "PromisedDelivery Date",
            "Promised Total Fee",
            "Total Paid",
            "Balance Amount",
            "Payment Count",
            "Payment %",
            "Stage",
            "Current Lead Stage",
            "Admission Stage",
            "Source",
            "Follow-up Date",
            "Next Follow-up",
            "Lead Owner",
            "Counsellor",
            "Employee ID",
            "Department",
            "Designation",
            "Exam Attended",
            "Certificate Delivered",
            "Certificate Status",
            "Remarks",
            "Notes",
            "Last Activity",
            "Created By",
            "Last Updated By",
            "Created At",
            "Updated At",
        ]
        for dt in doc_types:
            headers.append(f"Doc {DOC_TYPE_LABELS.get(dt, dt.value)} URL")
        headers.extend(
            [
                "Payments Summary",
                "Payment Receipt URLs",
            ]
        )

        from app.services.lead_sheet_fields import build_lead_sync_fields

        rows: list[list[Any]] = []
        for p in prospects:
            estimated = Decimal(str(p.estimated_deal_value or 0))
            total_paid = Decimal("0")
            payment_count = 0
            payment_lines: list[str] = []
            receipt_urls: list[str] = []

            for pay in p.payments or []:
                status_val = (
                    pay.payment_status.value
                    if hasattr(pay.payment_status, "value")
                    else str(pay.payment_status or "")
                )
                if status_val == PaymentStatus.completed.value:
                    total_paid += Decimal(str(pay.amount or 0))
                    payment_count += 1

                ptype = (
                    pay.payment_type.value
                    if hasattr(pay.payment_type, "value")
                    else str(pay.payment_type or "")
                )
                pmethod = (
                    pay.payment_method.value
                    if hasattr(pay.payment_method, "value")
                    else str(pay.payment_method or "")
                )
                receipt = ExportService._absolute_file_url(pay.receipt_url)
                payment_lines.append(
                    " | ".join(
                        [
                            pay.payment_id or "",
                            f"₹{pay.amount}",
                            ptype,
                            pmethod,
                            status_val,
                            str(pay.payment_date or ""),
                            (pay.notes or "").strip(),
                        ]
                    ).strip(" |")
                )
                if receipt:
                    receipt_urls.append(f"{pay.payment_id}: {receipt}")

            balance = estimated - total_paid
            if balance < 0:
                balance = Decimal("0")

            pct = (
                float((total_paid / estimated * Decimal("100")).quantize(Decimal("0.01")))
                if estimated > 0
                else 0.0
            )

            docs_by_type: dict[str, str] = {}
            for doc in p.documents or []:
                dtype = (
                    doc.document_type.value
                    if hasattr(doc.document_type, "value")
                    else str(doc.document_type)
                )
                url = ExportService._absolute_file_url(doc.file_url)
                if dtype in docs_by_type and docs_by_type[dtype]:
                    docs_by_type[dtype] = f"{docs_by_type[dtype]}\n{url}"
                else:
                    docs_by_type[dtype] = url

            assigned_name = ""
            assigned_code = ""
            if p.assigned_to:
                assigned_name = p.assigned_to.name or ""
                assigned_code = p.assigned_to.employee_id or ""

            course_name = ""
            if getattr(p, "course", None) is not None and p.course.name:
                course_name = (p.course.name or "").strip()
            elif p.course_id:
                course_name = course_names.get(p.course_id, "")

            stage_val = (
                p.stage.value if hasattr(p.stage, "value") else str(p.stage or "")
            )
            extra = build_lead_sync_fields(p, db=db)

            row: list[Any] = [
                p.prospect_id,
                p.name or "",
                p.email or "",
                p.phone or "",
                str(p.dob or ""),
                p.father_name or "",
                p.mother_name or "",
                course_name,
                p.specialization or "",
                extra.get("university", ""),
                p.address or "",
                p.delivery_address or "",
                str(p.delivery_date or ""),
                float(estimated),
                float(total_paid),
                float(balance),
                payment_count,
                pct,
                stage_val,
                extra.get("current_lead_stage", stage_val),
                extra.get("admission_stage", ""),
                p.source or "",
                extra.get("follow_up_date", ""),
                extra.get("next_follow_up", ""),
                extra.get("lead_owner", assigned_name),
                assigned_name,
                assigned_code,
                extra.get("department", ""),
                extra.get("designation", ""),
                extra.get("exam_attended", ""),
                extra.get("exam_certified", ""),
                extra.get("certificate_status", ""),
                extra.get("remarks", ""),
                p.notes or "",
                extra.get("last_activity", ""),
                extra.get("created_by", ""),
                extra.get("last_updated_by", ""),
                extra.get("created_at", str(p.created_at or "")),
                extra.get("updated_at", str(p.updated_at or "")),
            ]
            for dt in doc_types:
                row.append(docs_by_type.get(dt.value, ""))
            row.append("\n".join(payment_lines))
            row.append("\n".join(receipt_urls))
            rows.append(row)

        return ExportService._to_xlsx(
            headers,
            rows,
            "leads_export.xlsx",
            "Leads",
        )

    @staticmethod
    def export(
        db: Session,
        *,
        export_type: str,
        fmt: str,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        employee_id: Optional[int] = None,
        stage: Optional[str] = None,
        source: Optional[str] = None,
        current_user_id: Optional[int] = None,
        is_admin: bool = False,
    ) -> StreamingResponse:
        export_type = export_type.lower().strip()
        fmt = fmt.lower().strip()

        if fmt not in ("xlsx", "csv", "pdf"):
            raise ValueError("Unsupported format. Use xlsx, csv, or pdf.")

        if export_type not in (
            "leads",
            "employee_performance",
            "sales",
            "dashboard",
        ):
            raise ValueError(
                "Unsupported export_type. Use leads, employee_performance, sales, or dashboard."
            )

        # Employees can only export their own scoped data
        scoped_employee_id = employee_id
        if not is_admin:
            scoped_employee_id = current_user_id

        headers, rows, title = ExportService._build_dataset(
            db,
            export_type=export_type,
            date_from=date_from,
            date_to=date_to,
            employee_id=scoped_employee_id,
            stage=stage,
            source=source,
            is_admin=is_admin,
        )

        filename = f"{export_type}_export.{fmt}"

        if fmt == "csv":
            return ExportService._to_csv(headers, rows, filename)
        if fmt == "xlsx":
            return ExportService._to_xlsx(headers, rows, filename, title)
        return ExportService._to_pdf(headers, rows, filename, title)

    @staticmethod
    def _build_dataset(
        db: Session,
        *,
        export_type: str,
        date_from: Optional[date],
        date_to: Optional[date],
        employee_id: Optional[int],
        stage: Optional[str],
        source: Optional[str],
        is_admin: bool,
    ) -> tuple[list[str], list[list[Any]], str]:
        if export_type == "leads":
            prospects = AnalyticsRepository.list_leads_for_export(
                db,
                employee_id=employee_id,
                date_from=date_from,
                date_to=date_to,
                stage=stage,
                source=source,
            )
            headers = [
                "Prospect ID",
                "Name",
                "Email",
                "Phone",
                "Stage",
                "Source",
                "Counsellor",
                "Deal Value",
                "Follow-up Date",
                "Created At",
            ]
            rows = [
                [
                    p.prospect_id,
                    p.name,
                    p.email or "",
                    p.phone or "",
                    p.stage.value if hasattr(p.stage, "value") else str(p.stage),
                    p.source or "",
                    p.assigned_to_id or "",
                    float(p.estimated_deal_value or 0),
                    str(p.follow_up_date or ""),
                    str(p.created_at),
                ]
                for p in prospects
            ]
            return headers, rows, "Leads Export"

        if export_type == "employee_performance":
            data = AnalyticsRepository.employee_performance(
                db,
                date_from=date_from,
                date_to=date_to,
                employee_id=employee_id,
                stage=stage,
                source=source,
            )
            headers = [
                "Employee ID",
                "Employee Code",
                "Name",
                "Leads Assigned",
                "Leads Converted",
                "Revenue",
                "Conversion Rate (%)",
            ]
            rows = [
                [
                    d["employee_id"],
                    d["employee_code"] or "",
                    d["employee_name"],
                    d["leads_assigned"],
                    d["leads_converted"],
                    float(d["revenue"]),
                    d["conversion_rate"],
                ]
                for d in data
            ]
            return headers, rows, "Employee Performance"

        if export_type == "sales":
            monthly = AnalyticsRepository.monthly_sales(
                db,
                employee_id=employee_id,
                date_from=date_from,
                date_to=date_to,
            )
            headers = ["Month", "Year", "Revenue", "Deals"]
            rows = [
                [m["month"], m["year"], float(m["revenue"]), m.get("deals", 0)]
                for m in monthly
            ]
            return headers, rows, "Sales Report"

        # dashboard
        if is_admin and employee_id is None:
            dash = DashboardService.admin_dashboard(db, date_from, date_to)
            headers = ["Metric", "Value"]
            rows = [
                ["Total Employees", dash.total_employees],
                ["Total Leads", dash.total_leads],
                ["Total Revenue", float(dash.total_revenue)],
            ]
            for stage_item in dash.leads_by_stage:
                rows.append([f"Stage: {stage_item.stage}", stage_item.count])
            for perf in dash.top_performers:
                rows.append(
                    [
                        f"Top: {perf.employee_name}",
                        f"Revenue={float(perf.revenue)}, Converted={perf.leads_converted}",
                    ]
                )
            return headers, rows, "Admin Dashboard"

        emp_id = employee_id
        dash = DashboardService.employee_dashboard(db, emp_id, date_from, date_to)
        headers = ["Metric", "Value"]
        rows = [
            ["Leads Total", dash.lead_counts.total],
            ["Leads Today", dash.lead_counts.today],
            ["Leads This Week", dash.lead_counts.this_week],
            ["Leads This Month", dash.lead_counts.this_month],
            ["Advanced Paid Leads", dash.payment_status.advanced_paid],
            ["50% Paid Leads", dash.payment_status.fifty_percent_paid],
            ["100% Paid Leads", dash.payment_status.hundred_percent_paid],
            ["Collected Today", float(dash.payment_collected.today)],
            ["Collected This Week", float(dash.payment_collected.this_week)],
            ["Collected This Month", float(dash.payment_collected.this_month)],
            ["Collected Total", float(dash.payment_collected.total)],
        ]
        return headers, rows, "Employee Dashboard"

    @staticmethod
    def _to_csv(
        headers: list[str],
        rows: list[list[Any]],
        filename: str,
    ) -> StreamingResponse:
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(headers)
        writer.writerows(rows)
        buffer.seek(0)

        return StreamingResponse(
            iter([buffer.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @staticmethod
    def _to_xlsx(
        headers: list[str],
        rows: list[list[Any]],
        filename: str,
        title: str,
    ) -> StreamingResponse:
        try:
            from openpyxl import Workbook
        except ImportError as exc:
            raise ValueError(
                "openpyxl is required for Excel export. Install with: pip install openpyxl"
            ) from exc

        wb = Workbook()
        ws = wb.active
        ws.title = title[:31]
        ws.append(headers)
        for row in rows:
            ws.append(list(row))

        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)

        return StreamingResponse(
            buffer,
            media_type=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @staticmethod
    def _to_pdf(
        headers: list[str],
        rows: list[list[Any]],
        filename: str,
        title: str,
    ) -> StreamingResponse:
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import landscape, letter
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.platypus import (
                Paragraph,
                SimpleDocTemplate,
                Spacer,
                Table,
                TableStyle,
            )
        except ImportError as exc:
            raise ValueError(
                "reportlab is required for PDF export. Install with: pip install reportlab"
            ) from exc

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=landscape(letter))
        styles = getSampleStyleSheet()
        elements = [Paragraph(title, styles["Heading1"]), Spacer(1, 12)]

        data = [headers] + [[str(cell) for cell in row] for row in rows]
        table = Table(data, repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f4e79")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f2f2")]),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )
        elements.append(table)
        doc.build(elements)
        buffer.seek(0)

        return StreamingResponse(
            buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
