from datetime import date

import pytest

from app.models import UserRole

TOMORROW = date(2026, 10, 13)


@pytest.fixture
def manager(factory):
    return factory.user(UserRole.canteen_manager)


def test_manager_builds_dish_and_menu_student_sees_allergens(
    client, factory, auth, manager, freeze
):
    """Phase 2 «Готово, когда»: dish with a recipe goes on tomorrow's menu with right allergens."""
    freeze("2026-10-12 16:00")
    nuts = factory.allergen("nuts")
    gluten = factory.allergen("gluten")
    category = factory.category("Выпечка")
    factory.commit()
    h = auth(manager)
    walnut = client.post(
        "/api/v1/manager/ingredients",
        json={"name": "Грецкий орех", "unit": "g", "allergen_ids": [nuts.id]},
        headers=h,
    ).json()
    flour = client.post(
        "/api/v1/manager/ingredients",
        json={"name": "мука", "unit": "g", "allergen_ids": [gluten.id]},
        headers=h,
    ).json()
    honey = client.post(
        "/api/v1/manager/ingredients", json={"name": "мёд", "unit": "g"}, headers=h
    ).json()
    resp = client.post(
        "/api/v1/manager/dishes",
        json={
            "category_id": category.id,
            "name_ru": "Медовик",
            "base_price": "700",
            "shelf_life_hours": 24,
            "is_vegetarian": True,
            "ingredients": [
                {"ingredient_id": flour["id"], "quantity": "50"},
                {"ingredient_id": honey["id"], "quantity": "20"},
                {"ingredient_id": walnut["id"], "quantity": "10"},
            ],
        },
        headers=h,
    )
    assert resp.status_code == 201, resp.text
    dish = resp.json()
    assert {a["code"] for a in dish["allergens"]} == {"nuts", "gluten"}

    resp = client.put(
        "/api/v1/manager/menu?date=2026-10-13",
        json={"items": [{"dish_id": dish["id"], "price": "700", "planned_portions": 30}]},
        headers=h,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["items"][0]["available_portions"] == 30

    student = factory.user()
    factory.user_allergen(student, nuts)
    menu = client.get(
        f"/api/v1/canteens/{manager.canteen_id}/menu?date=2026-10-13", headers=auth(student)
    ).json()
    item = menu["items"][0]
    assert item["name_ru"] == "Медовик"
    assert {a["code"] for a in item["allergens"]} == {"nuts", "gluten"}
    assert item["unsafe_for_me"] is True


def test_update_recipe_changes_allergens(client, factory, auth, manager):
    milk = factory.allergen("milk")
    milky = factory.ingredient([milk])
    dish = factory.dish()
    resp = client.patch(
        f"/api/v1/manager/dishes/{dish.id}",
        json={"ingredients": [{"ingredient_id": milky.id, "quantity": "50"}], "base_price": "800"},
        headers=auth(manager),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["base_price"] == "800.00"
    assert [a["code"] for a in body["allergens"]] == ["milk"]
    resp = client.patch(
        f"/api/v1/manager/dishes/{dish.id}", json={"ingredients": []}, headers=auth(manager)
    )
    assert resp.json()["allergens"] == []


def test_dish_validation(client, factory, auth, manager):
    category = factory.category()
    factory.commit()
    resp = client.post(
        "/api/v1/manager/dishes",
        json={
            "category_id": category.id,
            "name_ru": "X",
            "base_price": "100",
            "ingredients": [{"ingredient_id": 999, "quantity": "1"}],
        },
        headers=auth(manager),
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "ingredient_not_found"
    resp = client.post(
        "/api/v1/manager/dishes",
        json={"category_id": category.id, "name_ru": "X", "base_price": "-1"},
        headers=auth(manager),
    )
    assert resp.status_code == 422


def test_duplicate_ingredient(client, factory, auth, manager):
    h = auth(manager)
    client.post("/api/v1/manager/ingredients", json={"name": "Рис", "unit": "g"}, headers=h)
    resp = client.post("/api/v1/manager/ingredients", json={"name": "рис", "unit": "g"}, headers=h)
    assert resp.status_code == 409
    listed = client.get("/api/v1/manager/ingredients", headers=h).json()
    assert [i["name"] for i in listed] == ["рис"]


def test_menu_put_updates_and_removes(client, factory, auth, manager, db):
    canteen_id = manager.canteen_id
    d1, d2 = factory.dish(), factory.dish()
    h = auth(manager)
    url = "/api/v1/manager/menu?date=2026-10-13"
    client.put(
        url,
        json={
            "items": [
                {"dish_id": d1.id, "price": "500", "planned_portions": 10},
                {"dish_id": d2.id, "price": "600", "planned_portions": 20},
            ]
        },
        headers=h,
    )
    resp = client.put(
        url, json={"items": [{"dish_id": d1.id, "price": "550", "planned_portions": 15}]}, headers=h
    )
    items = resp.json()["items"]
    assert [(i["dish_id"], i["price"], i["planned_portions"]) for i in items] == [
        (d1.id, "550.00", 15)
    ]
    assert client.get(url, headers=h).json()["canteen_id"] == canteen_id


def test_planned_keeps_taken_portions(client, factory, auth, manager):
    canteen = manager.canteen
    item = factory.menu_item(canteen, day=TOMORROW, portions=7, planned=10)  # 3 already taken
    h = auth(manager)
    resp = client.patch(
        f"/api/v1/manager/menu-items/{item.id}", json={"planned_portions": 20}, headers=h
    )
    assert resp.status_code == 200
    assert resp.json()["items"][0]["available_portions"] == 17
    resp = client.patch(
        f"/api/v1/manager/menu-items/{item.id}", json={"planned_portions": 2}, headers=h
    )
    assert resp.status_code == 409
    resp = client.patch(
        f"/api/v1/manager/menu-items/{item.id}", json={"available_portions": 25}, headers=h
    )
    assert resp.status_code == 422


def test_manager_cannot_touch_other_canteen(client, factory, auth, manager):
    other = factory.canteen()
    item = factory.menu_item(other, day=TOMORROW)
    h = auth(manager)
    assert (
        client.patch(f"/api/v1/manager/menu-items/{item.id}", json={"price": "1"}, headers=h)
    ).status_code == 404
    assert (
        client.get(f"/api/v1/manager/menu?date=2026-10-13&canteen_id={other.id}", headers=h)
    ).status_code == 403


def test_admin_picks_canteen(client, factory, auth):
    admin = factory.user(UserRole.admin)
    canteen = factory.canteen()
    factory.menu_item(canteen, day=TOMORROW)
    resp = client.get(
        f"/api/v1/manager/menu?date=2026-10-13&canteen_id={canteen.id}", headers=auth(admin)
    )
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 1


@pytest.mark.parametrize(
    "role", [UserRole.student, UserRole.teacher, UserRole.cook, UserRole.cashier]
)
@pytest.mark.parametrize(
    ("method", "url"),
    [
        ("get", "/api/v1/manager/dishes"),
        ("post", "/api/v1/manager/dishes"),
        ("get", "/api/v1/manager/ingredients"),
        ("post", "/api/v1/manager/ingredients"),
        ("get", "/api/v1/manager/menu?date=2026-10-13"),
        ("put", "/api/v1/manager/menu?date=2026-10-13"),
        ("patch", "/api/v1/manager/menu-items/1"),
        ("patch", "/api/v1/manager/dishes/1"),
    ],
)
def test_catalog_forbidden_for_other_roles(client, factory, auth, role, method, url):
    resp = getattr(client, method)(
        url, headers=auth(factory.user(role)), **({} if method == "get" else {"json": {}})
    )
    assert resp.status_code == 403
