from app.models import AllergySeverity, UserRole


def test_get_and_patch_profile(client, factory, auth):
    user = factory.user()
    other_group = factory.group("SE-9999")
    resp = client.patch(
        "/api/v1/me",
        json={
            "full_name": "Жанна Т.",
            "preferred_language": "kk",
            "group_id": other_group.id,
            "marketing_opt_out": True,
        },
        headers=auth(user),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["full_name"] == "Жанна Т."
    assert body["preferred_language"] == "kk"
    assert body["group_code"] == "SE-9999"
    assert body["marketing_opt_out"] is True


def test_teacher_cannot_set_group(client, factory, auth):
    teacher = factory.user(UserRole.teacher)
    resp = client.patch("/api/v1/me", json={"group_id": factory.group().id}, headers=auth(teacher))
    assert resp.status_code == 422


def test_staff_profile_shows_canteen(client, factory, auth):
    cook = factory.user(UserRole.cook)
    body = client.get("/api/v1/me", headers=auth(cook)).json()
    assert body["canteen_id"] == cook.canteen_id
    assert body["canteen_name"]


def test_allergens_need_consent(client, factory, auth):
    user = factory.user()
    nuts = factory.allergen("nuts")
    resp = client.put(
        "/api/v1/me/allergens",
        json={"consent": False, "allergens": [{"allergen_id": nuts.id, "severity": "severe"}]},
        headers=auth(user),
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "health_consent_required"


def test_set_and_revoke_allergens(client, factory, auth):
    user = factory.user()
    nuts, milk = factory.allergen("nuts"), factory.allergen("milk")
    resp = client.put(
        "/api/v1/me/allergens",
        json={
            "consent": True,
            "allergens": [
                {"allergen_id": nuts.id, "severity": "severe"},
                {"allergen_id": milk.id, "severity": "mild"},
            ],
        },
        headers=auth(user),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["health_data_consent_at"] is not None
    assert [(a["code"], a["severity"]) for a in body["allergens"]] == [
        ("nuts", AllergySeverity.severe),
        ("milk", AllergySeverity.mild),
    ]

    resp = client.delete("/api/v1/me/health-consent", headers=auth(user))
    assert resp.status_code == 200
    assert resp.json() == {"health_data_consent_at": None, "allergens": []}
    assert client.get("/api/v1/me/allergens", headers=auth(user)).json()["allergens"] == []


def test_allergens_are_private(client, factory, auth):
    owner = factory.user()
    factory.user_allergen(owner, factory.allergen("nuts"))
    other = factory.user()
    assert client.get("/api/v1/me/allergens", headers=auth(other)).json()["allergens"] == []
