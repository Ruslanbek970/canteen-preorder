def test_public_reference_lists(client, factory):
    canteen = factory.canteen(slug="main")
    factory.group("SE-2301")
    factory.allergen("nuts")
    assert [c["slug"] for c in client.get("/api/v1/canteens").json()] == ["main"]
    assert client.get("/api/v1/canteens/by-slug/main").json()["id"] == canteen.id
    assert client.get("/api/v1/canteens/by-slug/nope").status_code == 404
    assert [g["code"] for g in client.get("/api/v1/groups").json()] == ["SE-2301"]
    assert [a["code"] for a in client.get("/api/v1/allergens").json()] == ["nuts"]
