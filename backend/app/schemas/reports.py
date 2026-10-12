from datetime import date, datetime, time
from decimal import Decimal

from pydantic import BaseModel


class DashboardSlot(BaseModel):
    id: int
    starts_at: time
    ends_at: time
    capacity: int
    booked: int
    is_closed: bool


class Dashboard(BaseModel):
    date: date
    orders_total: int
    orders_by_status: dict[str, int]
    preorders: int
    cashier_sales: int
    revenue: Decimal
    portions_sold: int
    waste_portions: int
    waste_by_reason: dict[str, int]
    no_show: int
    no_show_percent: float | None
    proposed_promotions: int
    slots: list[DashboardSlot]
    synthetic_history_until: date | None


class SalesTotals(BaseModel):
    orders: int
    portions: int
    revenue: Decimal
    average_check: Decimal | None
    preorder_share: float | None


class SalesDay(BaseModel):
    date: date
    orders: int
    portions: int
    revenue: Decimal
    preorder_share: float | None


class SalesDish(BaseModel):
    dish_id: int
    name: str
    portions: int
    revenue: Decimal


class SalesReport(BaseModel):
    from_date: date
    to_date: date
    totals: SalesTotals
    days: list[SalesDay]
    dishes: list[SalesDish]
    synthetic_history_until: date | None


class WasteDay(BaseModel):
    date: date
    portions: int
    by_reason: dict[str, int]


class WasteDish(BaseModel):
    dish_id: int
    name: str
    portions: int
    planned: int
    percent_of_planned: float | None


class WasteReport(BaseModel):
    from_date: date
    to_date: date
    total: int
    per_day: float | None
    percent_of_planned: float | None
    by_reason: dict[str, int]
    days: list[WasteDay]
    dishes: list[WasteDish]
    synthetic_history_until: date | None


class PeakSlot(BaseModel):
    starts_at: time
    orders: int
    per_day: float
    load_percent: float | None


class PeakWeekday(BaseModel):
    weekday: int  # ISO: 1 = Monday
    orders: int
    per_day: float


class PeakReport(BaseModel):
    from_date: date
    to_date: date
    days: int
    no_show_percent: float | None
    slots: list[PeakSlot]
    weekdays: list[PeakWeekday]
    synthetic_history_until: date | None


class RatingComment(BaseModel):
    rating: int
    comment: str
    created_at: datetime


class DishRating(BaseModel):
    dish_id: int
    name: str
    rating: float | None
    count: int
    distribution: list[int]  # number of 1..5 star reviews
    last_comments: list[RatingComment]


class RatingsReport(BaseModel):
    from_date: date
    to_date: date
    dishes: list[DishRating]
    synthetic_history_until: date | None


class ForecastScore(BaseModel):
    model: str
    mae: float
    mape: float
    n: int


class ForecastDay(BaseModel):
    date: date
    actual: int
    forecast: int
    baseline_avg: float | None
    gbm_v1: float | None


class ForecastDish(BaseModel):
    dish_id: int
    dish_name: str
    actual: int
    forecast: int
    mae: float


class ForecastRunInfo(BaseModel):
    target_date: date
    run_at: datetime
    model: str
    mae: float | None
    mape: float | None
    backtest: list[ForecastScore]


class ForecastReport(BaseModel):
    from_date: date
    to_date: date
    synthetic_history_until: date | None
    days: list[ForecastDay]
    models: list[ForecastScore]
    served: ForecastScore | None
    better: str | None
    dishes: list[ForecastDish]
    upcoming: list[ForecastRunInfo]
