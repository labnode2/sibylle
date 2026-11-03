import re

import pytest

from sibylle.notify.email import Renderer

pytestmark = pytest.mark.unit

LINK = "https://sibylle.exemple.fr/rejoindre/jeton-de-test"
CASES = {
    "verify_email": ({"first_name": "Camille", "link": LINK}, "Confirme ton adresse pour Sibylle"),
    "reset_password": (
        {"first_name": "Camille", "link": LINK},
        "Ton lien pour changer de mot de passe",
    ),
    "invitation": (
        {
            "to": "cami@exemple.fr",
            "inviter_pseudo": "Inès",
            "org_title": "Sophia Office",
            "link": LINK,
        },
        "Inès t'invite dans la rédaction Sophia Office",
    ),
}


@pytest.mark.parametrize("template", sorted(CASES))
def test_transactional_emails_render(template: str) -> None:
    payload, subject = CASES[template]
    mail = Renderer().render(template, "cami@exemple.fr", payload)
    assert mail.subject == subject
    assert LINK in mail.text and LINK in mail.html
    # Nothing is loaded from elsewhere: no remote image, no stylesheet, no script.
    assert not re.search(r"<(img|link|script)\b", mail.html)
    assert "https://" not in mail.html.replace(LINK, "")


def test_html_escapes_what_members_typed() -> None:
    payload = {**CASES["invitation"][0], "org_title": "<b>Rédac</b>"}
    mail = Renderer().render("invitation", "x@exemple.fr", payload)
    assert "<b>Rédac</b>" not in mail.html
    assert "&lt;b&gt;Rédac&lt;/b&gt;" in mail.html


ORIGIN = "http://localhost:5173"
ABOUT = {
    "org_id": "org",
    "org_title": "Sophia Office",
    "prono_id": "prono",
    "question": "Nice ou Monaco samedi ?",
    "member_id": "membre",
}
NOTIFICATIONS = {
    "new_prono": {},
    "closing_soon": {},
    "result": {"kind": "resolution", "seq": 1, "result": "Nice", "outcome": "won", "payout": 1},
    "designation_reminder": {"relaunch": 0},
}


@pytest.mark.parametrize("type", sorted(NOTIFICATIONS))
def test_notification_emails_render(type: str) -> None:
    from sibylle.db.models import Notification
    from sibylle.notify.messages import email_values

    notification = Notification(type=type, payload={**ABOUT, **NOTIFICATIONS[type]})
    mail = Renderer().render(type, "cami@exemple.fr", email_values(notification, "fr"))
    assert mail.subject.startswith("Sophia Office · ")
    prono, prefs = f"{ORIGIN}/o/org/pronos/prono", f"{ORIGIN}/compte#notifications"
    for link in (prono, prefs):
        assert link in mail.text and link in mail.html
    assert "Nice ou Monaco samedi ?" in mail.html
    assert not re.search(r"<(img|link|script)\b", mail.html)
    assert not re.search(r"https?://(?!localhost:5173/)", mail.html)


def test_a_single_laurel_is_singular() -> None:
    from sibylle.db.models import Notification
    from sibylle.notify.messages import lead

    notification = Notification(type="result", payload={**ABOUT, **NOTIFICATIONS["result"]})
    assert lead(notification, "fr") == "Résultat : Nice. Tu gagnes 1 laurier."
