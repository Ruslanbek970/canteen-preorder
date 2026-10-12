from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query, Response

from app.api.deps import DB, ManagedCanteen
from app.schemas.reports import Dashboard, PeakReport, RatingsReport, SalesReport, WasteReport
from app.services import reports

router = APIRouter(prefix="/manager", tags=["reports"])

From = Annotated[date | None, Query(alias="from")]
To = Annotated[date | None, Query(alias="to")]


@router.get("/dashboard", response_model=Dashboard)
def dashboard(canteen_id: ManagedCanteen, db: DB) -> Dashboard:
    return reports.dashboard(db, canteen_id)


@router.get("/reports/sales", response_model=SalesReport)
def sales(canteen_id: ManagedCanteen, db: DB, from_: From = None, to: To = None) -> SalesReport:
    return reports.sales(db, canteen_id, *reports.period(from_, to))


@router.get("/reports/waste", response_model=WasteReport)
def waste(canteen_id: ManagedCanteen, db: DB, from_: From = None, to: To = None) -> WasteReport:
    return reports.waste(db, canteen_id, *reports.period(from_, to))


@router.get("/reports/peak-hours", response_model=PeakReport)
def peak_hours(canteen_id: ManagedCanteen, db: DB, from_: From = None, to: To = None) -> PeakReport:
    return reports.peak_hours(db, canteen_id, *reports.period(from_, to))


@router.get("/reports/ratings", response_model=RatingsReport)
def ratings(canteen_id: ManagedCanteen, db: DB, from_: From = None, to: To = None) -> RatingsReport:
    return reports.ratings(db, canteen_id, *reports.period(from_, to, days=56))


@router.get("/reports/{name}.csv")
def report_csv(
    name: str, canteen_id: ManagedCanteen, db: DB, from_: From = None, to: To = None
) -> Response:
    days = 56 if name == "ratings" else reports.DEFAULT_DAYS
    filename, body = reports.report_csv(db, canteen_id, name, *reports.period(from_, to, days))
    return Response(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
