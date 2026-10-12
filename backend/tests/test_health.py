from app.api.routers import health


def test_health_ok(client):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_ready_ok_when_dependencies_up(client, monkeypatch):
    monkeypatch.setattr(health, "check_db", lambda: True)
    monkeypatch.setattr(health, "check_redis", lambda: True)
    resp = client.get("/api/v1/health/ready")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_ready_503_when_db_down(client, monkeypatch):
    monkeypatch.setattr(health, "check_db", lambda: False)
    monkeypatch.setattr(health, "check_redis", lambda: True)
    resp = client.get("/api/v1/health/ready")
    assert resp.status_code == 503
    assert resp.json()["checks"] == {"db": False, "redis": True}
