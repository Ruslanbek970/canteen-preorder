import re

import pytest

from app.models import UserRole


def _register(client, **kw):
    body = {
        "email": "new@uni.kz",
        "password": "secret123",
        "full_name": "New Student",
        "role": "student",
        **kw,
    }
    return client.post("/api/v1/auth/register", json=body)


def _code(outbox) -> str:
    match = re.search(r"\b(\d{6})\b", outbox[-1]["body"])
    assert match
    return match.group(1)


def test_register_verify_and_login(client, factory, outbox):
    group = factory.group()
    resp = _register(client, group_id=group.id)
    assert resp.status_code == 201, resp.text
    assert outbox and outbox[-1]["to"] == "new@uni.kz"

    me_before = client.post(
        "/api/v1/auth/login", json={"email": "new@uni.kz", "password": "secret123"}
    ).json()
    headers = {"Authorization": f"Bearer {me_before['access_token']}"}
    assert client.get("/api/v1/me", headers=headers).json()["email_verified"] is False

    resp = client.post("/api/v1/auth/verify-email", json={"email": "new@uni.kz", "code": "000000"})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "invalid_code"

    resp = client.post(
        "/api/v1/auth/verify-email", json={"email": "new@uni.kz", "code": _code(outbox)}
    )
    assert resp.status_code == 200
    me = client.get("/api/v1/me", headers=headers).json()
    assert me["email_verified"] is True
    assert me["role"] == "student"
    assert me["group_id"] == group.id


def test_register_rejects_foreign_domain(client, factory):
    resp = _register(client, email="x@gmail.com", group_id=factory.group().id)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "email_domain_not_allowed"


def test_student_needs_group_teacher_does_not(client):
    assert _register(client).json()["error"]["code"] == "group_required"
    assert _register(client, role="teacher").status_code == 201


def test_staff_roles_cannot_self_register(client):
    assert _register(client, role="cook").status_code == 422


def test_duplicate_email(client, factory):
    factory.user(UserRole.teacher, email="dup@uni.kz")
    resp = _register(client, email="DUP@uni.kz", role="teacher")
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "email_taken"


def test_short_password_rejected(client):
    resp = _register(client, role="teacher", password="short")
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"


def test_code_attempts_are_limited(client, outbox):
    _register(client, role="teacher")
    code = _code(outbox)
    for _ in range(5):
        client.post("/api/v1/auth/verify-email", json={"email": "new@uni.kz", "code": "111111"})
    resp = client.post("/api/v1/auth/verify-email", json={"email": "new@uni.kz", "code": code})
    assert resp.status_code == 422


def test_resend_code(client, outbox):
    _register(client, role="teacher")
    client.post("/api/v1/auth/resend-code", json={"email": "new@uni.kz"})
    assert len(outbox) == 2
    resp = client.post(
        "/api/v1/auth/verify-email", json={"email": "new@uni.kz", "code": _code(outbox)}
    )
    assert resp.status_code == 200


def _login(client, email, password="demo1234"):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


def test_login_wrong_password(client, factory):
    user = factory.user()
    resp = _login(client, user.email, "wrong-password")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "invalid_credentials"


def test_blocked_user_cannot_login(client, factory):
    user = factory.user(is_active=False)
    assert _login(client, user.email).status_code == 403


def test_login_rate_limited(client, factory):
    user = factory.user()
    for _ in range(5):
        _login(client, user.email, "wrong-password")
    resp = _login(client, user.email)
    assert resp.status_code == 429
    assert resp.json()["error"]["code"] == "rate_limited"


def test_refresh_rotates_and_revokes(client, factory):
    user = factory.user()
    tokens = _login(client, user.email).json()
    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert resp.status_code == 200
    new_tokens = resp.json()
    assert new_tokens["refresh_token"] != tokens["refresh_token"]
    again = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert again.status_code == 401


def test_logout_revokes_refresh(client, factory):
    user = factory.user()
    tokens = _login(client, user.email).json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    resp = client.post(
        "/api/v1/auth/logout", json={"refresh_token": tokens["refresh_token"]}, headers=headers
    )
    assert resp.status_code == 200
    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert resp.status_code == 401


@pytest.mark.parametrize("header", [None, "Bearer garbage", "Basic abc"])
def test_me_requires_valid_token(client, header):
    headers = {"Authorization": header} if header else {}
    resp = client.get("/api/v1/me", headers=headers)
    assert resp.status_code == 401
    assert "error" in resp.json()


def test_expired_access_token(client, factory, monkeypatch):
    from app.config import get_settings

    user = factory.user()
    monkeypatch.setattr(get_settings(), "access_token_minutes", -1)
    tokens = _login(client, user.email).json()
    resp = client.get("/api/v1/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "token_expired"
