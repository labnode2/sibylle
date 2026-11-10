#!/usr/bin/env python3
"""Shows every page and e-mail of Sibylle's Keycloak theme, the way people reach them, and checks
each one: the page Keycloak meant, its title in Sibylle's frame and words, the files it loads.
A template error shows as a failed check. It needs a Keycloak started by keycloak/dev.sh (the
realm of dev-realm.json, its admin) and Mailpit (`make db`, or the CI's), and nothing but Python:

    python3 -I keycloak/check-theme.py

KEYCLOAK_URL (http://localhost:8280) and MAILPIT_URL (http://127.0.0.1:8025) point elsewhere.
"""

import html
import http.cookiejar
import json
import os
import pathlib
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

KEYCLOAK = os.environ.get("KEYCLOAK_URL", "http://localhost:8280").rstrip("/")
MAILPIT = os.environ.get("MAILPIT_URL", "http://127.0.0.1:8025").rstrip("/")
REALM = f"{KEYCLOAK}/realms/sibylle"
CLIENT = "sibylle-dev"
APP = "http://localhost:5173/"
ROOT = pathlib.Path(__file__).resolve().parent.parent

failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> bool:
    print(f"{'ok  ' if ok else 'FAIL'}  {name}{'' if ok else f': {detail}'}")
    if not ok:
        failures.append(name)
    return ok


class Page:
    def __init__(self, status: int, url: str, body: str) -> None:
        self.status, self.url, self.body = status, url, body

    @property
    def id(self) -> str:
        found = re.search(r'data-page-id="([^"]*)"', self.body)
        return found.group(1) if found else ""

    @property
    def title(self) -> str:
        found = re.search(r'<h1 class="title" id="kc-page-title">(.*?)</h1>', self.body, re.S)
        return html.unescape(found.group(1)).strip() if found else ""

    @property
    def to_app(self) -> bool:
        """Keycloak sent the browser back to the app, with a code."""
        return self.url.startswith(APP) and "code=" in self.url

    def form(self, form_id: str) -> str:
        found = re.search(rf'<form id="{form_id}"[^>]*action="([^"]*)"', self.body)
        return html.unescape(found.group(1)) if found else ""

    def link(self, text: str) -> str:
        for href, label in re.findall(r'<a [^>]*href="([^"]*)"[^>]*>(.*?)</a>', self.body, re.S):
            if html.unescape(label).strip() == text:
                return urllib.parse.urljoin(self.url, html.unescape(href))
        return ""

    def has(self, text: str) -> bool:
        return text in html.unescape(self.body)

    def error_of(self, field: str) -> str:
        found = re.search(rf'id="{field}-error"[^>]*>(.*?)</span>', self.body, re.S)
        return html.unescape(found.group(1)).strip() if found else ""

    def alert(self) -> str:
        found = re.search(r'<p class="alert-text">(.*?)</p>', self.body, re.S)
        return html.unescape(found.group(1)).strip() if found else ""


class StopRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return None


class LocalCookies(http.cookiejar.DefaultCookiePolicy):
    """Keycloak marks its cookies Secure; browsers still send them to http://localhost."""

    def return_ok_secure(self, cookie, request):  # type: ignore[no-untyped-def]
        return True


class Browser:
    """One person's browser: its cookies, and redirects followed until they leave Keycloak."""

    def __init__(self) -> None:
        jar = http.cookiejar.CookieJar(LocalCookies())
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(jar), StopRedirects()
        )

    def open(self, url: str, data: dict[str, str] | None = None) -> Page:
        for _ in range(10):
            body = urllib.parse.urlencode(data).encode() if data is not None else None
            try:
                with self.opener.open(urllib.request.Request(url, data=body), timeout=30) as resp:
                    return Page(resp.status, resp.geturl(), resp.read().decode())
            except urllib.error.HTTPError as err:
                if err.code not in (301, 302, 303, 307):
                    return Page(err.code, url, err.read().decode())
                url, data = urllib.parse.urljoin(url, err.headers["Location"]), None
                if not url.startswith(KEYCLOAK):
                    return Page(err.code, url, "")
        raise RuntimeError(f"too many redirects from {url}")

    def sign_in_page(self) -> Page:
        query = urllib.parse.urlencode(
            {"client_id": CLIENT, "redirect_uri": APP, "response_type": "code", "scope": "openid"}
        )
        return self.open(f"{REALM}/protocol/openid-connect/auth?{query}")


def expect(name: str, page: Page, page_id: str, title: str) -> bool:
    return check(
        name,
        page.id == page_id
        and page.title == title
        and page.has(f"<title>{title} · Sibylle</title>"),
        f"HTTP {page.status}, page {page.id or '?'!r}, title {page.title!r}, at {page.url}",
    )


def mail_to(address: str, subject: str) -> dict:
    """The last e-mail to an address with that subject, waited for a few seconds."""
    query = urllib.parse.urlencode({"query": f'to:"{address}" subject:"{subject}"', "limit": 1})
    for _ in range(20):
        with urllib.request.urlopen(f"{MAILPIT}/api/v1/search?{query}", timeout=10) as resp:
            messages = json.load(resp)["messages"]
        if messages:
            with urllib.request.urlopen(
                f"{MAILPIT}/api/v1/message/{messages[0]['ID']}", timeout=10
            ) as resp:
                return json.load(resp)
        time.sleep(0.5)
    return {}


def check_mail(name: str, address: str, subject: str, words: list[str]) -> str:
    """Checks an e-mail's two versions and gives its link."""
    mail = mail_to(address, subject)
    if not check(f"e-mail {name}", bool(mail), f"no e-mail « {subject} » to {address} in Mailpit"):
        return ""
    text, page = mail.get("Text", ""), html.unescape(mail.get("HTML", ""))
    missing = [w for w in ["LA GAZETTE DE", *words] if w not in page] + [
        w for w in words[:1] if w not in text
    ]
    check(f"e-mail {name}: words", not missing, f"missing {missing}")
    found = re.search(r"https?://\S+/login-actions/action-token\?\S+", text)
    check(f"e-mail {name}: link", bool(found), "no action link in the text version")
    return found.group(0) if found else ""


def admin(method: str, path: str, body: object | None = None) -> object:
    """Keycloak's admin API, as the local admin of keycloak/dev.sh."""
    if not hasattr(admin, "token"):
        data = urllib.parse.urlencode(
            {
                "grant_type": "password",
                "client_id": "admin-cli",
                "username": "admin",
                "password": "admin",
            }
        ).encode()
        with urllib.request.urlopen(
            f"{KEYCLOAK}/realms/master/protocol/openid-connect/token", data, timeout=30
        ) as resp:
            admin.token = json.load(resp)["access_token"]  # type: ignore[attr-defined]
    request = urllib.request.Request(
        f"{KEYCLOAK}/admin/realms/sibylle{path}",
        method=method,
        data=None if body is None else json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {admin.token}", "Content-Type": "application/json"},  # type: ignore[attr-defined]
    )
    with urllib.request.urlopen(request, timeout=30) as resp:
        raw = resp.read()
        return json.loads(raw) if raw else None


def user_id(email: str) -> str:
    users = admin("GET", f"/users?{urllib.parse.urlencode({'email': email, 'exact': 'true'})}")
    return users[0]["id"]  # type: ignore[index]


def files_of(page: Page) -> None:
    """Everything the page loads from the theme, and the fonts its style sheet loads, answer."""
    paths = set(re.findall(r'(?:href|src)="(/resources/[^"]+)"', page.body))
    paths |= set(re.findall(r'from "(/resources/[^"]+)"', page.body))
    broken = []
    for path in sorted(paths):
        url = KEYCLOAK + path
        try:
            with urllib.request.urlopen(url, timeout=30) as resp:
                content = resp.read().decode(errors="replace")
        except urllib.error.HTTPError as err:
            broken.append(f"{path} ({err.code})")
            continue
        for font in (
            re.findall(r"url\('([^']+\.woff2)'\)", content) if path.endswith(".css") else []
        ):
            try:
                urllib.request.urlopen(urllib.parse.urljoin(url, font), timeout=30).close()
            except urllib.error.HTTPError as err:
                broken.append(f"{font} ({err.code})")
    check(
        f"files of the sign-in page ({len(paths)} and their fonts)", not broken, f"broken: {broken}"
    )


def main() -> None:
    try:
        urllib.request.urlopen(f"{REALM}/.well-known/openid-configuration", timeout=10).close()
    except OSError as err:
        sys.exit(f"No Keycloak at {KEYCLOAK} ({err}): start it with keycloak/dev.sh start.")
    try:
        urllib.request.urlopen(f"{MAILPIT}/api/v1/info", timeout=10).close()
    except OSError as err:
        sys.exit(f"No Mailpit at {MAILPIT} ({err}): start it with make db.")

    kit = ROOT / "crystal-ball-kit/src/crystal-ball.js"
    copy = ROOT / "keycloak/theme/login/resources/js/crystal-ball.js"
    check(
        "crystal-ball.js is the kit's",
        kit.read_bytes() == copy.read_bytes(),
        f"copy {kit} to {copy}",
    )

    # Connexion, and a wrong password.
    person = Browser()
    login = person.sign_in_page()
    expect("sign-in page", login, "login-login", "Connexion")
    files_of(login)
    check(
        "sign-in page: no EMILE",
        "EMILE" not in login.body and "kc-emile" not in login.body,
        "EMILE is still on the sign-in page",
    )
    wrong = person.open(
        login.form("kc-form-login"), {"username": "camille@sibylle.test", "password": "pas-le-bon"}
    )
    check(
        "wrong password: the note, both fields marked",
        wrong.alert() == "E-mail ou mot de passe incorrect."
        and wrong.body.count('aria-invalid="true"') == 2,
        f"note {wrong.alert()!r}",
    )

    # Créer un compte: the errors of an empty form, then a new account.
    signup = person.open(login.link("Créer un compte"))
    expect("sign-up page", signup, "login-register", "Créer un compte")
    check(
        "sign-up page: one password field, its copy made on submit",
        'data-confirmed-by="password-confirm"' in signup.body and "<noscript>" in signup.body,
    )
    empty = person.open(
        signup.form("kc-register-form"),
        {"firstName": "", "lastName": "", "email": "", "password": "", "password-confirm": ""},
    )
    errors = {name: empty.error_of(name) for name in ("firstName", "lastName", "email", "password")}
    check("sign-up errors under each field", all(errors.values()), f"errors {errors}")
    email = f"check-{uuid.uuid4().hex[:8]}@sibylle.test"
    password = f"gazette-{uuid.uuid4().hex[:8]}"
    created = person.open(
        empty.form("kc-register-form"),
        {
            "firstName": "Alex",
            "lastName": "Durand",
            "email": email,
            "password": password,
            "password-confirm": password,
        },
    )
    check(
        "sign-up: the new account goes back to the app", created.to_app, f"ended at {created.url}"
    )

    # Mot de passe oublié: the e-mail, its link, the new password.
    reader = Browser()
    forgot = reader.open(reader.sign_in_page().link("Mot de passe oublié ?"))
    expect("forgotten password page", forgot, "login-login-reset-password", "Mot de passe oublié")
    sent = reader.open(forgot.form("kc-reset-password-form"), {"username": email})
    check(
        "forgotten password: the note on the sign-in page",
        sent.id == "login-login"
        and sent.alert() == "Si un compte existe avec cette adresse, un lien vient de partir.",
        f"page {sent.id!r}, note {sent.alert()!r}",
    )
    link = check_mail(
        "new password",
        email,
        "Ton lien pour changer de mot de passe",
        ["Bonjour Alex,", "Choisir un nouveau mot de passe"],
    )
    if link:
        new = reader.open(link)
        expect("new password page", new, "login-login-update-password", "Nouveau mot de passe")
        short = reader.open(
            new.form("kc-passwd-update-form"),
            {"password-new": "court", "password-confirm": "court"},
        )
        check(
            "new password too short: under the field",
            short.error_of("password-new").startswith("Trop court"),
            f"error {short.error_of('password-new')!r}",
        )
        password = f"gazette-{uuid.uuid4().hex[:8]}"
        done = reader.open(
            short.form("kc-passwd-update-form"),
            {"password-new": password, "password-confirm": password, "logout-sessions": "on"},
        )
        check("new password: back to the app", done.to_app, f"ended at {done.url}")

    # A new password asked at sign-in (dev-realm.json's second account).
    asked = Browser()
    first = asked.sign_in_page()
    required = asked.open(
        first.form("kc-form-login"),
        {"username": "dominique@sibylle.test", "password": "gazette-dominique"},
    )
    expect(
        "new password asked at sign-in",
        required,
        "login-login-update-password",
        "Nouveau mot de passe",
    )

    # The page of a step left behind: the sign-in form sent after going to the sign-up.
    late = Browser()
    old = late.sign_in_page()
    late.open(old.link("Créer un compte"))
    expired = late.open(old.form("kc-form-login"))
    expect("expired page", expired, "login-login-page-expired", "Cette page a expiré")

    # An error (an app Keycloak does not know), the sign-out to confirm.
    query = urllib.parse.urlencode(
        {"client_id": "nobody", "redirect_uri": APP, "response_type": "code", "scope": "openid"}
    )
    error = Browser().open(f"{REALM}/protocol/openid-connect/auth?{query}")
    expect("error page", error, "login-error", "Un problème est survenu")
    logout = Browser().open(f"{REALM}/protocol/openid-connect/logout")
    expect("sign-out page", logout, "login-logout-confirm", "Te déconnecter ?")

    # E-mails the app asks Keycloak to send: the address to confirm, then actions.
    target = urllib.parse.urlencode({"client_id": CLIENT, "redirect_uri": APP})
    admin("PUT", f"/users/{user_id(email)}/send-verify-email?{target}")
    link = check_mail(
        "address check",
        email,
        "Confirme ton adresse pour Sibylle",
        ["Bonjour Alex,", "Confirmer mon adresse"],
    )
    if link:
        visitor = Browser()
        confirm = visitor.open(link)
        if expect("address check: confirm first", confirm, "login-info", "Confirme ton adresse"):
            check(
                "address check: the address",
                confirm.has(f"Pour confirmer l'adresse {email}, continue."),
            )
        confirmed = visitor.open(confirm.link("Continuer"))
        if expect("address check: confirmed", confirmed, "login-info", "Compte à jour"):
            check(
                "address check: the word and the way back",
                confirmed.has("C'est fait : ton compte est à jour.")
                and bool(confirmed.link("Retour à Sibylle")),
            )
    admin("PUT", f"/users/{user_id(email)}/execute-actions-email?{target}", ["UPDATE_PASSWORD"])
    link = check_mail(
        "actions",
        email,
        "Ton compte Sibylle t'attend",
        ["Bonjour Alex,", "choisir un mot de passe"],
    )
    if link:
        visitor = Browser()
        start = visitor.open(link)
        if expect("actions: what to do", start, "login-info", "Avant de continuer"):
            check("actions: the list", start.has("Choisir un nouveau mot de passe"))
        step = visitor.open(start.link("Continuer"))
        expect(
            "actions: the new password", step, "login-login-update-password", "Nouveau mot de passe"
        )

    # Required actions at sign-in: a profile to complete, then the address to confirm.
    other = f"check-{uuid.uuid4().hex[:8]}@sibylle.test"
    admin(
        "POST",
        "/users",
        {
            "username": other,
            "email": other,
            "firstName": "Sacha",
            "enabled": True,
            "requiredActions": ["UPDATE_PROFILE", "VERIFY_EMAIL"],
            "credentials": [{"type": "password", "value": password, "temporary": False}],
        },
    )
    newcomer = Browser()
    profile = newcomer.open(
        newcomer.sign_in_page().form("kc-form-login"), {"username": other, "password": password}
    )
    expect("profile to complete", profile, "login-login-update-profile", "Ton compte")
    check(
        "profile to complete: the names side by side",
        '<div class="row">' in profile.body and profile.has("TES NOM ET PRÉNOM RESTENT PRIVÉS"),
    )
    verify = newcomer.open(
        profile.form("kc-update-profile-form"),
        {"firstName": "Sacha", "lastName": "Leroy", "email": other},
    )
    expect(
        "address to confirm at sign-in", verify, "login-login-verify-email", "Confirme ton adresse"
    )

    print()
    if failures:
        sys.exit(f"{len(failures)} check(s) failed.")
    print("Every page and e-mail of the theme shows.")


if __name__ == "__main__":
    main()
