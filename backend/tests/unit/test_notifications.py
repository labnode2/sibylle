from datetime import UTC, datetime, timedelta

import pytest

from sibylle.domain.notifications import (
    allowed_push_endpoint,
    reminder_base,
    reminder_step,
)

pytestmark = pytest.mark.unit

BASE = datetime(2026, 11, 7, 18, 0, tzinfo=UTC)
DAY = timedelta(days=1)


@pytest.mark.parametrize(
    ("elapsed", "step"),
    [
        (-timedelta(minutes=1), None),
        (timedelta(0), 0),
        (DAY - timedelta(seconds=1), 0),
        (DAY, 1),
        (3 * DAY, 2),
        (7 * DAY - timedelta(seconds=1), 2),
        (7 * DAY, 3),
        (13 * DAY, 3),
        (14 * DAY, 4),
        (21 * DAY, 5),
    ],
)
def test_reminders_on_the_day_then_one_three_and_seven_days_later_then_weekly(
    elapsed: timedelta, step: int | None
) -> None:
    assert reminder_step(BASE, BASE + elapsed) == step


def test_the_schedule_starts_at_the_expected_result_or_the_day_after_the_closing() -> None:
    closes_at = BASE - 2 * DAY
    assert reminder_base(closes_at=closes_at, result_expected_at=BASE) == BASE
    assert reminder_base(closes_at=closes_at, result_expected_at=None) == closes_at + DAY
    assert reminder_base(closes_at=None, result_expected_at=None) is None


@pytest.mark.parametrize(
    ("endpoint", "allowed"),
    [
        ("https://fcm.googleapis.com/fcm/send/abc", True),
        ("https://updates.push.services.mozilla.com/wpush/v2/abc", True),
        ("https://web.push.apple.com/abc", True),
        ("https://wns2-par02p.notify.windows.com/w/?token=abc", True),
        ("http://fcm.googleapis.com/fcm/send/abc", False),
        ("https://localhost/abc", False),
        ("https://10.0.0.1/abc", False),
        ("https://evilgoogleapis.com/abc", False),
        ("https://fcm.googleapis.com:8443/abc", False),
        ("https://user@fcm.googleapis.com/abc", False),
        ("pas une adresse", False),
    ],
)
def test_push_endpoints_are_the_browsers_push_services(endpoint: str, allowed: bool) -> None:
    assert allowed_push_endpoint(endpoint) is allowed
