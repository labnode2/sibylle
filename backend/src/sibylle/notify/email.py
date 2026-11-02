"""E-mails: rendered from Jinja2 templates (text and HTML), sent over SMTP.

Mailpit catches them in development; Brevo's SMTP relay sends them in production. The HTML
never loads anything from elsewhere: no remote image, no tracking pixel.
"""

from dataclasses import dataclass, field
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Protocol

import aiosmtplib
from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from sibylle.config import Settings, get_settings
from sibylle.i18n import DEFAULT_LOCALE, t

TEMPLATES = Path(__file__).parent / "templates"


@dataclass(frozen=True)
class Mail:
    to: str
    subject: str
    text: str
    html: str


class Renderer:
    def __init__(self, template_dir: Path = TEMPLATES) -> None:
        self.env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape(["html"]),
            undefined=StrictUndefined,
            keep_trailing_newline=True,
        )

    def render(
        self, template: str, to: str, context: dict[str, Any], locale: str = DEFAULT_LOCALE
    ) -> Mail:
        values = {"public_origin": get_settings().public_origin, **context}
        return Mail(
            to=to,
            subject=t(f"email.subject.{template}", locale, **values),
            text=self.env.get_template(f"{locale}/{template}.txt").render(values),
            html=self.env.get_template(f"{locale}/{template}.html").render(values),
        )


class Sender(Protocol):
    async def send(self, mail: Mail) -> None: ...


class SmtpSender:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def send(self, mail: Mail) -> None:
        message = EmailMessage()
        message["From"] = self.settings.mail_from
        message["To"] = mail.to
        message["Subject"] = mail.subject
        message.set_content(mail.text)
        message.add_alternative(mail.html, subtype="html")
        port = self.settings.smtp_port
        await aiosmtplib.send(
            message,
            hostname=self.settings.smtp_host,
            port=port,
            username=self.settings.smtp_user or None,
            password=self.settings.smtp_password or None,
            use_tls=port == 465,
            start_tls=True if port == 587 else None,
        )


@dataclass
class MemorySender:
    """Keeps the mails instead of sending them (tests)."""

    sent: list[Mail] = field(default_factory=list)
    fail: bool = False

    async def send(self, mail: Mail) -> None:
        if self.fail:
            raise ConnectionError("SMTP unavailable")
        self.sent.append(mail)
