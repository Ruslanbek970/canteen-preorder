import anyio.to_thread
from fastapi.testclient import TestClient

from app.main import create_app, db_threads


def test_thread_pool_is_capped_to_the_db_pool():
    with TestClient(create_app()) as client:
        tokens = client.portal.call(
            lambda: anyio.to_thread.current_default_thread_limiter().total_tokens
        )
    assert tokens == db_threads() == 20
