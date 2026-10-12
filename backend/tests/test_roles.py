"""require_roles and the demo accounts (phase 1 «Готово, когда»)."""

from typing import Annotated

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.errors import install_error_handlers
from app.models import User, UserRole
from app.security import require_roles


@pytest.fixture
def role_app() -> TestClient:
    app = FastAPI()
    install_error_handlers(app)

    @app.get("/kitchen")
    def kitchen(
        user: Annotated[User, Depends(require_roles(UserRole.cook, UserRole.canteen_manager))],
    ) -> dict[str, str]:
        return {"role": user.role.value}

    return TestClient(app)


@pytest.mark.parametrize(
    ("role", "status"),
    [
        (UserRole.cook, 200),
        (UserRole.canteen_manager, 200),
        (UserRole.student, 403),
        (UserRole.teacher, 403),
        (UserRole.cashier, 403),
        (UserRole.admin, 403),
    ],
)
def test_require_roles(role_app, factory, auth, role, status):
    resp = role_app.get("/kitchen", headers=auth(factory.user(role)))
    assert resp.status_code == status
    if status == 403:
        assert resp.json()["error"]["code"] == "forbidden"


def test_require_roles_needs_token(role_app):
    assert role_app.get("/kitchen").status_code == 401


DEMO = {
    "student@demo.kz": "student",
    "teacher@demo.kz": "teacher",
    "cook@demo.kz": "cook",
    "cashier@demo.kz": "cashier",
    "manager@demo.kz": "canteen_manager",
    "admin@demo.kz": "admin",
}


def test_seed_demo_accounts_log_in(client, db):
    from scripts import seed

    seed.run(db)
    for email, role in DEMO.items():
        resp = client.post("/api/v1/auth/login", json={"email": email, "password": "demo1234"})
        assert resp.status_code == 200, email
        me = client.get(
            "/api/v1/me", headers={"Authorization": f"Bearer {resp.json()['access_token']}"}
        ).json()
        assert me["role"] == role
        assert me["email_verified"] is True
        if role in ("cook", "cashier", "canteen_manager"):
            assert me["canteen_id"] is not None
