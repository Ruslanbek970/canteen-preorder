from datetime import date
from decimal import Decimal

import pytest

from app.models import DishReview, Order, OrderStatus, UserRole, WasteReason, WasteRecord
from app.schemas.orders import OrderCreate, OrderItemIn
from app.services import orders, payments, reports
from app.services.order_status import Actor, change_status

DAY = date(2026, 10, 12)


@pytest.fixture
def rep(db, factory, freeze):
    """Today: two pre-orders (one picked up, one no-show) and one unpaid order."""
    freeze("2026-10-12 10:00")
    canteen = factory.canteen()
    manager = factory.user(UserRole.canteen_manager, canteen=canteen)
    cashier = factory.user(UserRole.cashier, canteen=canteen)
    s12 = factory.slot(canteen, day=DAY, starts="12:00", capacity=10)
    s13 = factory.slot(canteen, day=DAY, starts="13:00", capacity=10)
    plov = factory.menu_item(
        canteen, factory.dish(name_ru="Плов", price=1500), day=DAY, portions=10
    )
    tea = factory.menu_item(canteen, factory.dish(name_ru="Чай", price=200), day=DAY, portions=10)

    def order(slot, lines, final):
        out = orders.create_order(
            db,
            factory.user(UserRole.teacher),
            OrderCreate(
                canteen_id=canteen.id,
                pickup_slot_id=slot.id,
                items=[OrderItemIn(menu_item_id=mi.id, quantity=q) for mi, q in lines],
            ),
        )
        if final == OrderStatus.pending_payment:
            return db.get(Order, out.id)
        payments.settle(db, out.payment_id, True, f"rep-{out.id}")
        o = db.get(Order, out.id)
        for step in (OrderStatus.cooking, OrderStatus.ready):
            change_status(db, o, step, Actor.kitchen)
        change_status(
            db, o, final, Actor.pickup if final == OrderStatus.picked_up else Actor.system
        )
        db.commit()
        return o

    done = order(s12, [(plov, 2), (tea, 1)], OrderStatus.picked_up)  # 3200
    no_show = order(s12, [(plov, 1)], OrderStatus.no_show)  # 1500, paid
    order(s13, [(tea, 1)], OrderStatus.pending_payment)
    db.add(
        WasteRecord(
            menu_item_id=plov.id,
            portions=1,
            reason=WasteReason.uncollected_order,
            order_id=no_show.id,
        )
    )
    db.add(WasteRecord(menu_item_id=plov.id, portions=3, reason=WasteReason.expired))
    db.add(DishReview(order_item_id=done.items[0].id, rating=5, comment="Отлично"))
    db.add(DishReview(order_item_id=done.items[1].id, rating=3))
    db.commit()
    return {"canteen": canteen, "manager": manager, "cashier": cashier, "plov": plov, "tea": tea}


def test_dashboard(client, auth, rep):
    client.post(
        "/api/v1/pos/sales",
        json={"items": [{"menu_item_id": rep["tea"].id, "quantity": 2}], "method": "cash"},
        headers=auth(rep["cashier"]),
    )
    d = client.get("/api/v1/manager/dashboard", headers=auth(rep["manager"])).json()
    assert d["date"] == "2026-10-12"
    assert d["orders_by_status"]["picked_up"] == 2 and d["orders_by_status"]["no_show"] == 1
    assert d["orders_by_status"]["pending_payment"] == 1
    assert d["preorders"] == 2 and d["cashier_sales"] == 1
    assert Decimal(d["revenue"]) == Decimal("5100")  # 3200 + 1500 + 400
    assert d["portions_sold"] == 6
    assert d["waste_portions"] == 4 and d["waste_by_reason"]["expired"] == 3
    assert d["no_show"] == 1 and d["no_show_percent"] == 50.0
    assert [(s["starts_at"], s["booked"]) for s in d["slots"]] == [("12:00:00", 2), ("13:00:00", 1)]
    assert d["synthetic_history_until"] is None


def test_sales_report_and_csv(client, auth, rep):
    h = auth(rep["manager"])
    s = client.get("/api/v1/manager/reports/sales?from=2026-10-12&to=2026-10-12", headers=h).json()
    assert s["totals"]["orders"] == 2 and s["totals"]["portions"] == 4
    assert Decimal(s["totals"]["revenue"]) == Decimal("4700")
    assert Decimal(s["totals"]["average_check"]) == Decimal("2350.00")
    assert s["totals"]["preorder_share"] == 100.0
    assert [(x["name"], x["portions"]) for x in s["dishes"]] == [("Плов", 3), ("Чай", 1)]
    assert s["days"] == [
        {
            "date": "2026-10-12",
            "orders": 2,
            "portions": 4,
            "revenue": "4700.00",
            "preorder_share": 100.0,
        }
    ]
    r = client.get("/api/v1/manager/reports/sales.csv?from=2026-10-12&to=2026-10-12", headers=h)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"]
    lines = r.content.decode("utf-8-sig").splitlines()
    assert lines[0] == "date,dish,portions,revenue"
    assert lines[1] == "2026-10-12,Плов,3,4500.00"


def test_waste_peak_and_ratings(client, auth, rep):
    h = auth(rep["manager"])
    w = client.get("/api/v1/manager/reports/waste", headers=h).json()
    assert w["total"] == 4 and w["by_reason"]["expired"] == 3
    assert w["by_reason"]["uncollected_order"] == 1  # the no-show
    assert w["percent_of_planned"] == 20.0 and w["per_day"] == 4.0
    assert w["dishes"][0] == {
        "dish_id": rep["plov"].dish_id,
        "name": "Плов",
        "portions": 4,
        "planned": 10,
        "percent_of_planned": 40.0,
    }

    p = client.get("/api/v1/manager/reports/peak-hours", headers=h).json()
    assert p["days"] == 1 and p["no_show_percent"] == 50.0
    assert p["slots"] == [
        {"starts_at": "12:00:00", "orders": 2, "per_day": 2.0, "load_percent": 20.0}
    ]
    assert p["weekdays"] == [{"weekday": 1, "orders": 2, "per_day": 2.0}]

    rt = client.get("/api/v1/manager/reports/ratings", headers=h).json()
    assert [(d["name"], d["rating"], d["distribution"]) for d in rt["dishes"]] == [
        ("Плов", 5.0, [0, 0, 0, 0, 1]),
        ("Чай", 3.0, [0, 0, 1, 0, 0]),
    ]
    assert rt["dishes"][0]["last_comments"][0]["comment"] == "Отлично"
    for name in ("waste", "peak-hours", "ratings"):
        r = client.get(f"/api/v1/manager/reports/{name}.csv", headers=h)
        assert r.status_code == 200 and len(r.text.splitlines()) >= 2


def test_access_and_validation(client, auth, factory, rep):
    for role in (UserRole.student, UserRole.cook, UserRole.cashier):
        h = auth(factory.user(role))
        assert client.get("/api/v1/manager/dashboard", headers=h).status_code == 403
        assert client.get("/api/v1/manager/reports/sales", headers=h).status_code == 403
        assert client.get("/api/v1/manager/reports/sales.csv", headers=h).status_code == 403
    other = auth(factory.user(UserRole.canteen_manager))
    assert (
        client.get("/api/v1/manager/reports/sales", headers=other).json()["totals"]["orders"] == 0
    )
    r = client.get(f"/api/v1/manager/reports/sales?canteen_id={rep['canteen'].id}", headers=other)
    assert r.status_code == 403
    admin = auth(factory.user(UserRole.admin))
    r = client.get(f"/api/v1/manager/reports/sales?canteen_id={rep['canteen'].id}", headers=admin)
    assert r.json()["totals"]["orders"] == 2

    h = auth(rep["manager"])
    bad = client.get("/api/v1/manager/reports/sales?from=2026-10-12&to=2026-10-01", headers=h)
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "invalid_period"
    long = client.get("/api/v1/manager/reports/sales?from=2024-01-01&to=2026-10-01", headers=h)
    assert long.json()["error"]["code"] == "period_too_long"
    assert client.get("/api/v1/manager/reports/nope.csv", headers=h).status_code == 404


def test_default_period():
    assert reports.period(None, date(2026, 10, 12)) == (date(2026, 9, 15), date(2026, 10, 12))
