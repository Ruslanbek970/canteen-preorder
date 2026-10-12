from datetime import date, timedelta

from app.models import AllergySeverity, Promotion, PromotionStatus, PromotionType, UserRole
from app.utils import time as clock

DAY = date(2026, 10, 12)


def test_menu_shows_allergens_from_recipe(client, factory, freeze):
    freeze("2026-10-12 10:00")
    canteen = factory.canteen()
    nuts, milk = factory.allergen("nuts"), factory.allergen("milk")
    cake = factory.dish(name_ru="Медовик", allergens=[nuts, milk])
    factory.menu_item(canteen, cake, day=DAY, portions=0, planned=30)
    factory.menu_item(canteen, factory.dish(name_ru="Плов"), day=DAY)

    body = client.get(f"/api/v1/canteens/{canteen.id}/menu").json()
    assert body["date"] == "2026-10-12"
    assert body["available_dates"] == ["2026-10-12"]
    by_name = {i["name_ru"]: i for i in body["items"]}
    assert {a["code"] for a in by_name["Медовик"]["allergens"]} == {"nuts", "milk"}
    assert by_name["Плов"]["allergens"] == []
    # sold out dishes stay visible
    assert by_name["Медовик"]["available_portions"] == 0
    assert by_name["Медовик"]["unsafe_for_me"] is False


def test_flags_for_signed_in_user(client, factory, auth, freeze):
    freeze("2026-10-12 10:00")
    canteen = factory.canteen()
    nuts, milk = factory.allergen("nuts"), factory.allergen("milk")
    factory.menu_item(canteen, factory.dish(name_ru="Медовик", allergens=[nuts]), day=DAY)
    factory.menu_item(canteen, factory.dish(name_ru="Чай", allergens=[milk]), day=DAY)
    user = factory.user()
    factory.user_allergen(user, nuts, AllergySeverity.severe)
    factory.user_allergen(user, milk, AllergySeverity.mild)

    items = client.get(f"/api/v1/canteens/{canteen.id}/menu", headers=auth(user)).json()["items"]
    by_name = {i["name_ru"]: i for i in items}
    assert by_name["Медовик"]["unsafe_for_me"] is True
    assert by_name["Медовик"]["my_allergens"] == ["nuts"]
    assert by_name["Чай"]["unsafe_for_me"] is False
    assert by_name["Чай"]["warning_for_me"] is True


def test_allergies_ignored_without_consent(client, factory, auth, freeze, db):
    freeze("2026-10-12 10:00")
    canteen = factory.canteen()
    nuts = factory.allergen("nuts")
    factory.menu_item(canteen, factory.dish(allergens=[nuts]), day=DAY)
    user = factory.user()
    factory.user_allergen(user, nuts)
    user.health_data_consent_at = None
    db.commit()
    item = client.get(f"/api/v1/canteens/{canteen.id}/menu", headers=auth(user)).json()["items"][0]
    assert item["unsafe_for_me"] is False


def test_tomorrow_only_after_15(client, factory, freeze):
    canteen = factory.canteen()
    factory.menu_item(canteen, day=DAY + timedelta(days=1))
    freeze("2026-10-12 14:59")
    resp = client.get(f"/api/v1/canteens/{canteen.id}/menu?date=2026-10-13")
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "menu_date_unavailable"
    freeze("2026-10-12 15:00")
    body = client.get(f"/api/v1/canteens/{canteen.id}/menu?date=2026-10-13").json()
    assert body["available_dates"] == ["2026-10-12", "2026-10-13"]
    assert len(body["items"]) == 1


def test_today_uses_almaty_date(client, factory, freeze):
    canteen = factory.canteen()
    factory.menu_item(canteen, day=DAY)
    # 00:30 in Almaty is still the previous day in UTC
    freeze("2026-10-12 00:30")
    assert client.get(f"/api/v1/canteens/{canteen.id}/menu").json()["date"] == "2026-10-12"


def test_leftover_discount_price(client, factory, freeze, db):
    now = freeze("2026-10-12 14:00")
    canteen = factory.canteen()
    item = factory.menu_item(canteen, day=DAY, price=450)
    for percent, status in ((30, PromotionStatus.active), (50, PromotionStatus.proposed)):
        db.add(
            Promotion(
                type=PromotionType.leftover,
                menu_item_id=item.id,
                discount_percent=percent,
                valid_from=now - timedelta(hours=1),
                valid_to=now + timedelta(hours=1),
                status=status,
            )
        )
    db.commit()
    body = client.get(f"/api/v1/canteens/{canteen.id}/menu").json()["items"][0]
    assert body["discount_percent"] == 30
    assert body["price"] == "450.00"
    assert body["price_now"] == "315"


def test_inactive_canteen_and_dish_card(client, factory, freeze):
    freeze("2026-10-12 10:00")
    canteen = factory.canteen(is_active=False)
    assert client.get(f"/api/v1/canteens/{canteen.id}/menu").status_code == 404
    nuts = factory.allergen("nuts")
    dish = factory.dish(name_ru="Медовик", allergens=[nuts], calories=420)
    card = client.get(f"/api/v1/dishes/{dish.id}").json()
    assert card["calories"] == 420
    assert [a["code"] for a in card["allergens"]] == ["nuts"]
    assert len(card["ingredients"]) == 1
    assert card["rating"] is None
    assert client.get("/api/v1/dishes/9999").status_code == 404


def test_today_local_helper():
    assert clock.today_local() == clock.now_local().date()


def test_staff_can_view_menu(client, factory, auth, freeze):
    freeze("2026-10-12 10:00")
    cook = factory.user(UserRole.cook)
    assert (
        client.get(f"/api/v1/canteens/{cook.canteen_id}/menu", headers=auth(cook)).status_code
        == 200
    )
