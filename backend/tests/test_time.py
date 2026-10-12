from app.utils.time import now_local, today_local


def test_now_local_is_almaty():
    now = now_local()
    assert now.tzinfo is not None
    assert now.utcoffset().total_seconds() == 5 * 3600


def test_today_local_matches_now_local():
    assert today_local() == now_local().date()
