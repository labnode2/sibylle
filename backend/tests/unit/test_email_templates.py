import re

import pytest

from sybille.notify.email import Renderer

pytestmark = pytest.mark.unit

LINK = "https://sybille.exemple.fr/rejoindre/jeton-de-test"
CASES = {
    "verify_email": ({"first_name": "Camille", "link": LINK}, "Confirme ton adresse pour Sybille"),
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
