import smtplib

from app.config import get_settings
from app.notifications import email


class FakeSMTP:
    calls: list[str] = []

    def __init__(self, host, port, timeout):
        self.calls.append(f"connect {host}:{port}")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self):
        self.calls.append("starttls")

    def login(self, user, password):
        self.calls.append(f"login {user}")

    def send_message(self, msg):
        self.calls.append(f"send {msg['To']} {msg['Subject']}")


def test_plain_smtp_in_dev(monkeypatch):
    FakeSMTP.calls = []
    monkeypatch.setattr(email.smtplib, "SMTP", FakeSMTP)
    assert email.send_email("a@uni.kz", "Код", "123456")
    assert FakeSMTP.calls == ["connect mailpit:1025", "send a@uni.kz Код"]


def test_production_smtp_with_login(monkeypatch):
    FakeSMTP.calls = []
    monkeypatch.setattr(email.smtplib, "SMTP", FakeSMTP)
    settings = get_settings()
    for key, value in {
        "smtp_host": "smtp.mail.kz",
        "smtp_port": 587,
        "smtp_user": "noreply",
        "smtp_password": "secret",
        "smtp_starttls": True,
    }.items():
        monkeypatch.setattr(settings, key, value)
    assert email.send_email("a@uni.kz", "Код", "123456")
    assert FakeSMTP.calls == [
        "connect smtp.mail.kz:587",
        "starttls",
        "login noreply",
        "send a@uni.kz Код",
    ]


def test_smtp_errors_do_not_break_the_request(monkeypatch):
    class Refusing(FakeSMTP):
        def send_message(self, msg):
            raise smtplib.SMTPRecipientsRefused({})

    monkeypatch.setattr(email.smtplib, "SMTP", Refusing)
    assert email.send_email("a@uni.kz", "Код", "123456") is False
