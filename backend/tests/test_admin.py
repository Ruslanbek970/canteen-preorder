from datetime import date

import pytest
from sqlalchemy import select

from app.models import ClassSchedule, RefreshToken, User, UserRole
from app.services import admin

DAY = date(2026, 10, 12)  # Monday


@pytest.fixture
def boss(factory):
    return factory.user(UserRole.admin)


def test_admin_endpoints_are_admin_only(client, auth, factory):
    for role in (UserRole.student, UserRole.cook, UserRole.canteen_manager):
        h = auth(factory.user(role))
        assert client.get("/api/v1/admin/users", headers=h).status_code == 403
        assert client.post("/api/v1/admin/groups", json={"code": "X"}, headers=h).status_code == 403
    assert client.get("/api/v1/admin/canteens").status_code == 401


def test_list_and_search_users_without_health_data(client, auth, factory, boss):
    canteen = factory.canteen(name="Главная")
    factory.user(UserRole.cook, canteen=canteen, full_name="Айгуль Повар")
    allergic = factory.user(full_name="Ерлан Студент")
    factory.user_allergen(allergic, factory.allergen("nuts"))
    h = auth(boss)
    data = client.get("/api/v1/admin/users?q=айгуль", headers=h).json()
    assert data["total"] == 1 and data["items"][0]["canteen_name"] == "Главная"
    students = client.get("/api/v1/admin/users?role=student", headers=h).json()
    assert [u["full_name"] for u in students["items"]] == ["Ерлан Студент"]
    assert "allerg" not in str(students).lower() and "health" not in str(students).lower()
    page = client.get("/api/v1/admin/users?limit=1&offset=1", headers=h).json()
    assert page["total"] == 3 and len(page["items"]) == 1


def test_create_staff(client, auth, db, factory, boss):
    canteen = factory.canteen()
    h = auth(boss)
    body = {
        "full_name": "Новый Кассир",
        "email": "New.Cashier@uni.kz",
        "password": "demo12345",
        "role": "cashier",
        "canteen_id": canteen.id,
    }
    r = client.post("/api/v1/admin/users", json=body, headers=h)
    assert r.status_code == 201
    out = r.json()
    assert out["email"] == "new.cashier@uni.kz" and out["email_verified"] is True
    login = client.post(
        "/api/v1/auth/login", json={"email": "new.cashier@uni.kz", "password": "demo12345"}
    )
    assert login.status_code == 200
    assert client.post("/api/v1/admin/users", json=body, headers=h).status_code == 409
    no_canteen = {**body, "email": "c2@uni.kz", "canteen_id": None}
    r = client.post("/api/v1/admin/users", json=no_canteen, headers=h)
    assert r.status_code == 422 and r.json()["error"]["code"] == "canteen_required"
    student = {**body, "email": "s@uni.kz", "role": "student"}
    r = client.post("/api/v1/admin/users", json=student, headers=h)
    assert r.json()["error"]["code"] == "group_required"


def test_change_role_block_and_self_protection(client, auth, db, factory, boss):
    canteen = factory.canteen()
    user = factory.user(UserRole.teacher)
    h = auth(boss)
    login = client.post("/api/v1/auth/login", json={"email": user.email, "password": "demo1234"})
    refresh = login.json()["refresh_token"]

    r = client.patch(
        f"/api/v1/admin/users/{user.id}",
        json={"role": "cook", "canteen_id": canteen.id},
        headers=h,
    )
    assert r.status_code == 200 and r.json()["role"] == "cook"
    # The new role signs them out everywhere.
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": refresh}).status_code == 401

    r = client.patch(f"/api/v1/admin/users/{user.id}", json={"role": "teacher"}, headers=h)
    assert r.json()["canteen_id"] is None  # not staff any more

    r = client.patch(f"/api/v1/admin/users/{user.id}", json={"is_active": False}, headers=h)
    assert r.json()["is_active"] is False
    login = client.post("/api/v1/auth/login", json={"email": user.email, "password": "demo1234"})
    assert login.status_code in (401, 403)
    assert db.scalar(select(RefreshToken.revoked_at).where(RefreshToken.user_id == user.id))

    for change in ({"is_active": False}, {"role": "teacher"}):
        r = client.patch(f"/api/v1/admin/users/{boss.id}", json=change, headers=h)
        assert r.status_code == 409 and r.json()["error"]["code"] == "self_lockout"
    assert client.patch("/api/v1/admin/users/99999", json={}, headers=h).status_code == 404


def test_new_password(client, auth, factory, boss):
    user = factory.user()
    r = client.patch(
        f"/api/v1/admin/users/{user.id}", json={"password": "another123"}, headers=auth(boss)
    )
    assert r.status_code == 200
    ok = client.post("/api/v1/auth/login", json={"email": user.email, "password": "another123"})
    assert ok.status_code == 200


def test_canteens_buildings_groups(client, auth, factory, boss):
    h = auth(boss)
    b = client.post("/api/v1/admin/buildings", json={"name": "Корпус Б"}, headers=h)
    assert b.status_code == 201
    building_id = b.json()["id"]
    assert (
        client.post("/api/v1/admin/buildings", json={"name": "Корпус Б"}, headers=h).status_code
        == 409
    )
    assert [x["name"] for x in client.get("/api/v1/admin/buildings", headers=h).json()] == [
        "Корпус Б"
    ]

    body = {"building_id": building_id, "name": "Кафе", "opens_at": "08:00", "closes_at": "16:00"}
    c = client.post("/api/v1/admin/canteens", json=body, headers=h)
    assert c.status_code == 201 and c.json()["default_slot_capacity"] == 30
    cid = c.json()["id"]
    bad = client.post("/api/v1/admin/canteens", json={**body, "opens_at": "17:00"}, headers=h)
    assert bad.status_code == 422
    r = client.patch(
        f"/api/v1/admin/canteens/{cid}",
        json={"default_slot_capacity": 40, "slug": "cafe", "is_active": False},
        headers=h,
    )
    assert r.json()["default_slot_capacity"] == 40 and r.json()["is_active"] is False
    r = client.patch(f"/api/v1/admin/canteens/{cid}", json={"closes_at": "07:00"}, headers=h)
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_hours"
    assert client.get("/api/v1/canteens").json() == []  # inactive ones are hidden from students

    g = client.post(
        "/api/v1/admin/groups",
        json={"code": "se-2302", "faculty": "ИТ", "study_year": 2},
        headers=h,
    )
    assert g.status_code == 201 and g.json()["code"] == "SE-2302"
    assert (
        client.post("/api/v1/admin/groups", json={"code": "SE-2302"}, headers=h).status_code == 409
    )
    groups = client.get("/api/v1/admin/groups", headers=h).json()
    assert groups == [
        {
            "id": g.json()["id"],
            "code": "SE-2302",
            "faculty": "ИТ",
            "study_year": 2,
            "students": 0,
            "lessons": 0,
        }
    ]


CSV = """group_code,day_of_week,starts_at,ends_at,building,subject
SE-2301,1,09:00,10:20,Главный корпус,Математика
SE-2301,1,10:30,11:50,Главный корпус,
SE-2301,3,9:00,10:20,главный корпус,Физика
"""


@pytest.fixture
def campus(factory):
    group = factory.group("SE-2301")
    building = factory.building("Главный корпус")
    return group, building


def test_schedule_import_replaces_the_groups_timetable(db, factory, campus):
    group, building = campus
    other = factory.group("IS-2201")
    factory.lesson(group, 5, "15:00", "16:20")  # replaced
    factory.lesson(other, 2, "09:00", "10:20")  # another group: kept
    preview = admin.import_schedule(db, CSV.encode(), dry_run=True)
    assert preview.errors == [] and not preview.imported
    assert (preview.rows, preview.groups, preview.deleted, preview.created) == (
        3,
        ["SE-2301"],
        1,
        3,
    )
    assert len(db.scalars(select(ClassSchedule)).all()) == 2  # dry run writes nothing

    result = admin.import_schedule(db, ("﻿" + CSV).encode(), dry_run=False)
    assert result.imported
    lessons = db.scalars(
        select(ClassSchedule).where(ClassSchedule.group_id == group.id).order_by(ClassSchedule.id)
    ).all()
    assert [(x.day_of_week, x.starts_at.isoformat(), x.subject) for x in lessons] == [
        (1, "09:00:00", "Математика"),
        (1, "10:30:00", None),
        (3, "09:00:00", "Физика"),
    ]
    assert db.scalar(select(ClassSchedule).where(ClassSchedule.group_id == other.id))


def test_schedule_import_reports_every_bad_line_and_writes_nothing(db, campus):
    text = "\n".join(
        [
            "group_code;day_of_week;starts_at;ends_at;building;subject",
            "SE-2301;1;09:00;10:20;Главный корпус;ok",
            "XX-1;1;09:00;10:20;Главный корпус;",
            "SE-2301;8;09:00;10:20;Главный корпус;",
            "SE-2301;2;9.00;10:20;Главный корпус;",
            "SE-2301;2;11:00;10:20;Главный корпус;",
            "SE-2301;2;12:00;13:00;Корпус Х;",
            "SE-2301;1;09:00;10:00;Главный корпус;",
            "SE-2301;1",
        ]
    )
    result = admin.import_schedule(db, text.encode(), dry_run=False)
    assert not result.imported
    assert [(e.line, e.code) for e in result.errors] == [
        (3, "unknown_group"),
        (4, "day_of_week"),
        (5, "time"),
        (6, "time_order"),
        (7, "unknown_building"),
        (8, "duplicate"),
        (9, "columns"),
    ]
    assert db.scalar(select(ClassSchedule)) is None
    assert admin.import_schedule(db, b"", dry_run=True).errors[0].code == "empty"
    assert admin.import_schedule(db, "Ж".encode("cp1251"), dry_run=True).errors[0].code == (
        "encoding"
    )


def test_imported_timetable_changes_the_students_slots(client, auth, db, factory, freeze, campus):
    """SPEC phase 10: the admin imports a timetable, the group's students see new slots."""
    freeze("2026-10-12 08:00")
    group, _building = campus
    canteen = factory.canteen()
    for start in ("09:30", "12:00"):
        factory.slot(canteen, day=DAY, starts=start)
    student = factory.user(group=group)
    h = auth(student)

    def suitable():
        data = client.get(f"/api/v1/canteens/{canteen.id}/slots?date={DAY}", headers=h).json()
        return [s["starts_at"][:5] for s in data["slots"]]

    assert suitable() == ["09:30", "12:00"]
    upload = client.post(
        "/api/v1/admin/schedule/import",
        files={"file": ("schedule.csv", CSV.encode(), "text/csv")},
        headers=auth(factory.user(UserRole.admin)),
    )
    assert upload.status_code == 200 and upload.json()["imported"] is True
    assert suitable() == ["12:00"]  # 09:30 is during the first lesson now
    assert db.get(User, student.id).group_id == group.id


def test_schedule_upload_limits(client, auth, factory):
    h = auth(factory.user(UserRole.admin))
    big = b"x" * 1_000_001
    r = client.post(
        "/api/v1/admin/schedule/import", files={"file": ("a.csv", big, "text/csv")}, headers=h
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "file_too_large"
    r = client.post(
        "/api/v1/admin/schedule/import?dry_run=true",
        files={"file": ("a.csv", CSV.encode(), "text/csv")},
        headers=h,
    )
    assert r.json()["errors"][0]["code"] == "unknown_group"
