import os
import sys
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))
from db import init_db, upsert_operator, insert_snapshot, save_subscription, get_all_subscriptions
import main


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "test.db")
    init_db(path)
    upsert_operator(path, "AV8313426653583", "Tesla", "AV8313426653583")
    return path


def test_notify_sends_push_on_change(db_path, tmp_path):
    insert_snapshot(db_path, "AV8313426653583", 100, "Model Y", "Authorized", "{}")
    insert_snapshot(db_path, "AV8313426653583", 110, "Model Y", "Authorized", "{}")
    save_subscription(db_path, "https://push.apple.com/test", "p256dh", "auth")

    fake_key = tmp_path / "private_key.pem"
    fake_key.write_text("fake")

    with patch("main.webpush") as mock_push, \
         patch("main.VAPID_PRIVATE_KEY_PATH", str(fake_key)):
        main.notify_if_changed(db_path)

    mock_push.assert_called_once()
    call_kwargs = mock_push.call_args[1]
    assert "Tesla 차량 10대 증가 (100 → 110)" in call_kwargs["data"]


def test_notify_skips_when_no_change(db_path, tmp_path):
    insert_snapshot(db_path, "AV8313426653583", 100, "Model Y", "Authorized", "{}")
    insert_snapshot(db_path, "AV8313426653583", 100, "Model Y", "Authorized", "{}")
    save_subscription(db_path, "https://push.apple.com/test", "p256dh", "auth")

    fake_key = tmp_path / "private_key.pem"
    fake_key.write_text("fake")

    with patch("main.webpush") as mock_push, \
         patch("main.VAPID_PRIVATE_KEY_PATH", str(fake_key)):
        main.notify_if_changed(db_path)

    mock_push.assert_not_called()


def test_notify_deletes_expired_subscription(db_path, tmp_path):
    from pywebpush import WebPushException
    insert_snapshot(db_path, "AV8313426653583", 100, "Model Y", "Authorized", "{}")
    insert_snapshot(db_path, "AV8313426653583", 110, "Model Y", "Authorized", "{}")
    save_subscription(db_path, "https://push.apple.com/test", "p256dh", "auth")

    fake_key = tmp_path / "private_key.pem"
    fake_key.write_text("fake")

    expired_response = MagicMock()
    expired_response.status_code = 410
    exc = WebPushException("Gone", response=expired_response)

    with patch("main.webpush", side_effect=exc), \
         patch("main.VAPID_PRIVATE_KEY_PATH", str(fake_key)):
        main.notify_if_changed(db_path)

    assert get_all_subscriptions(db_path) == []
