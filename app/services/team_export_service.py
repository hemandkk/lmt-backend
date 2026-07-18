"""Dedicated exports for /api/v1/team/exports (not shared with /exports)."""

from __future__ import annotations

import csv
import io
from datetime import date
from typing import Any, Optional

from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.models.user import User
from app.services.team_service import TeamService


class TeamExportService:

    @staticmethod
    def export(
        db: Session,
        viewer: User,
        *,
        export_type: str,
        fmt: str,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        employee_id: Optional[int] = None,
        supervisor_id: Optional[int] = None,
    ) -> StreamingResponse:
        export_type = export_type.lower().strip()
        fmt = fmt.lower().strip()
        if fmt not in ("xlsx", "csv"):
            raise ValueError("Unsupported format. Use xlsx or csv.")
        if export_type not in (
            "sales",
            "performance",
            "payments",
            "analytics",
        ):
            raise ValueError(
                "exportType must be sales, performance, payments, or analytics."
            )

        headers, rows, title = TeamExportService._dataset(
            db,
            viewer,
            export_type=export_type,
            date_from=date_from,
            date_to=date_to,
            employee_id=employee_id,
            supervisor_id=supervisor_id,
        )
        filename = f"team_{export_type}_export.{fmt}"
        if fmt == "csv":
            return TeamExportService._to_csv(headers, rows, filename)
        return TeamExportService._to_xlsx(headers, rows, filename, title)

    @staticmethod
    def _dataset(
        db: Session,
        viewer: User,
        *,
        export_type: str,
        date_from: Optional[date],
        date_to: Optional[date],
        employee_id: Optional[int],
        supervisor_id: Optional[int],
    ) -> tuple[list[str], list[list[Any]], str]:
        if export_type == "performance":
            data = TeamService.performance(
                db,
                viewer,
                date_from=date_from,
                date_to=date_to,
                employee_id=employee_id,
                supervisor_id=supervisor_id,
            )
            headers = [
                "Employee ID",
                "Employee Code",
                "Name",
                "Admissions",
                "Converted",
                "Collection",
                "Monthly Target",
                "Target Revenue",
                "Converted Deal Value",
                "Conversion Rate %",
                "Performance Status",
            ]
            rows = [
                [
                    i["employee_id"],
                    i["employee_code"] or "",
                    i["employee_name"] or "",
                    i["admissions"],
                    i["leads_converted"],
                    float(i["collection"]),
                    float(i["monthly_target"]),
                    float(i["target_revenue"]),
                    float(i["converted_deal_value"]),
                    i["conversion_rate"],
                    i["performance_status"],
                ]
                for i in data["items"]
            ]
            return headers, rows, "Team Performance"

        if export_type == "sales":
            data = TeamService.sales(
                db,
                viewer,
                date_from=date_from,
                date_to=date_to,
                employee_id=employee_id,
                supervisor_id=supervisor_id,
            )
            headers = ["Metric", "Value"]
            rows = [
                ["Total Revenue", float(data["total_revenue"])],
                ["Total Admissions", data["total_admissions"]],
                ["Leads Converted", data["leads_converted"]],
                ["Conversion Rate %", data["conversion_rate"]],
            ]
            for m in data["monthly"]:
                rows.append(
                    [
                        f"{m['year']}-{int(m['month']):02d}",
                        f"Revenue={m['revenue']}, Deals={m['deals']}",
                    ]
                )
            return headers, rows, "Team Sales"

        if export_type == "payments":
            data = TeamService.payments(
                db,
                viewer,
                date_from=date_from,
                date_to=date_to,
                employee_id=employee_id,
                supervisor_id=supervisor_id,
            )
            headers = ["Metric", "Value"]
            c = data["collected"]
            rows = [
                ["Total Collected (period)", float(data["total_collected"])],
                ["Collected Today", c.get("today")],
                ["Collected This Week", c.get("thisWeek")],
                ["Collected This Month", c.get("thisMonth")],
                ["Collected Total", c.get("total")],
                [
                    "Advanced Paid Leads",
                    data["lead_payment_status"].get("advancedPaid"),
                ],
                [
                    "50% Paid Leads",
                    data["lead_payment_status"].get("fiftyPercentPaid"),
                ],
                [
                    "100% Paid Leads",
                    data["lead_payment_status"].get("hundredPercentPaid"),
                ],
            ]
            return headers, rows, "Team Payments"

        # analytics
        data = TeamService.analytics(
            db,
            viewer,
            date_from=date_from,
            date_to=date_to,
            employee_id=employee_id,
            supervisor_id=supervisor_id,
        )
        headers = ["Metric", "Value"]
        rows = [
            ["Total Admissions", data["total_admissions"]],
            ["Total Revenue", float(data["total_revenue"])],
            ["Conversion Rate %", data["conversion_rate"]],
            ["Exam Attended", data["exam_stats"].get("attended")],
            ["Exam Certified", data["exam_stats"].get("certified")],
            ["Exam Pending", data["exam_stats"].get("pending")],
        ]
        for s in data["leads_by_stage"]:
            rows.append([f"Stage: {s['stage']}", s["count"]])
        return headers, rows, "Team Analytics"

    @staticmethod
    def _to_csv(
        headers: list[str], rows: list[list[Any]], filename: str
    ) -> StreamingResponse:
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(headers)
        writer.writerows(rows)
        buffer.seek(0)
        return StreamingResponse(
            iter([buffer.getvalue()]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            },
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
                "openpyxl is required for Excel export."
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
                "application/vnd.openxmlformats-officedocument"
                ".spreadsheetml.sheet"
            ),
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            },
        )
