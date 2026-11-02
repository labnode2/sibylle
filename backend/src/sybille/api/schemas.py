"""Request and response bodies (contracts/rest-api.md). Responses never carry a member's name,
first name or e-mail, except `Me`, which is the account's own."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal, Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, model_validator

from sybille.db.models import Account, Membership, Organisation

EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

Email = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=254, pattern=EMAIL_PATTERN)
]
Password = Annotated[str, StringConstraints(min_length=8, max_length=200)]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
Pseudo = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=24)]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
Role = Literal["reader", "journalist", "editor"]
Theme = Literal["auto", "light", "dark"]


class PixelImage(BaseModel):
    size: Literal[16, 32]
    palette: Literal["base-v1"]
    pixels: str


# Responses


class OrgCard(BaseModel):
    id: uuid.UUID
    title: str
    logo: PixelImage | None
    background_key: str

    @classmethod
    def of(cls, org: Organisation) -> Self:
        return cls.model_validate(org, from_attributes=True)


class MemberPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    pseudo: str
    avatar: PixelImage
    frame: str | None = None
    role: Role
    joined_at: datetime

    @classmethod
    def of(cls, member: Membership) -> Self:
        return cls.model_validate(member, from_attributes=True)


class MemberSelf(MemberPublic):
    balance: int
    season_score: int
    unlocked_colors: list[int] = []


class MembershipEntry(BaseModel):
    org: OrgCard
    membership: MemberSelf


class Me(BaseModel):
    id: uuid.UUID
    email: str
    first_name: str
    last_name: str
    email_verified: bool
    theme: Theme
    reduce_motion: bool
    locale: str
    memberships: list[MembershipEntry]

    @classmethod
    def of(cls, account: Account, memberships: list[tuple[Organisation, Membership]]) -> Self:
        return cls(
            id=account.id,
            email=account.email or "",
            first_name=account.first_name or "",
            last_name=account.last_name or "",
            email_verified=account.email_verified_at is not None,
            theme=account.theme,
            reduce_motion=account.reduce_motion,
            locale=account.locale,
            memberships=[
                MembershipEntry(org=OrgCard.of(org), membership=MemberSelf.of(member))
                for org, member in memberships
            ],
        )


class Org(OrgCard):
    starting_balance: int
    max_base_gain: int
    early_bird_pct: int
    early_bird_count: int
    editor_note: str | None
    charter: str
    # Only the editor sees the access code.
    access_code: str | None
    member_count: int
    my_membership: MemberSelf

    @classmethod
    def build(cls, org: Organisation, me: Membership, member_count: int) -> Self:
        return cls(
            **OrgCard.of(org).model_dump(),
            starting_balance=org.starting_balance,
            max_base_gain=org.max_base_gain,
            early_bird_pct=org.early_bird_pct,
            early_bird_count=org.early_bird_count,
            editor_note=org.editor_note,
            charter=org.charter,
            access_code=org.access_code if me.role == "editor" else None,
            member_count=member_count,
            my_membership=MemberSelf.of(me),
        )


class OrgCreated(BaseModel):
    org: Org
    membership: MemberSelf


class InvitationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: Literal["link", "email"]
    email: str | None
    max_uses: int
    use_count: int
    places_left: int
    expires_at: datetime
    revoked_at: datetime | None
    created_at: datetime


class InvitationCreated(BaseModel):
    invitation: InvitationOut
    # Shown once, for links only: the token is never stored in clear.
    url: str | None


class JoinPreview(BaseModel):
    org: OrgCard
    member_count: int
    places_left: int | None
    invited_by_pseudo: str | None
    charter: str
    already_member: bool


class Joined(BaseModel):
    org: OrgCard
    membership: MemberSelf


# Requests


class SignupIn(BaseModel):
    email: Email
    password: Password
    first_name: Name
    last_name: Name


class LoginIn(BaseModel):
    email: str
    password: str


class MePatch(BaseModel):
    first_name: Name | None = None
    last_name: Name | None = None
    theme: Theme | None = None
    reduce_motion: bool | None = None
    locale: Literal["fr"] | None = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: Password


class TokenIn(BaseModel):
    token: str


class ResetRequest(BaseModel):
    email: str


class ResetConfirm(BaseModel):
    token: str
    password: Password


class OrgIn(BaseModel):
    title: Title
    background_key: str
    logo: PixelImage | None = None
    pseudo: Pseudo
    avatar: PixelImage


class MemberPatch(BaseModel):
    pseudo: Pseudo | None = None
    avatar: PixelImage | None = None


class LinkInvitationIn(BaseModel):
    kind: Literal["link"]
    max_uses: int = Field(ge=1, le=500)
    expires_at: AwareDatetime


class EmailInvitationIn(BaseModel):
    kind: Literal["email"]
    email: Email


InvitationIn = Annotated[LinkInvitationIn | EmailInvitationIn, Field(discriminator="kind")]


class JoinSource(BaseModel):
    token: str | None = None
    code: str | None = None

    @model_validator(mode="after")
    def _one_source(self) -> Self:
        if bool(self.token) == bool(self.code):
            raise ValueError("give either an invitation token or an access code")
        return self


class JoinIn(JoinSource):
    pseudo: Pseudo
    avatar: PixelImage
    charter_accepted: Literal[True]


def drawing(image: PixelImage | None) -> dict[str, Any] | None:
    return image.model_dump() if image else None


# Pronos and bets

Kind = Literal["choice", "yes_no", "number", "date"]
PronoState = Literal["proposed", "rejected", "scheduled", "open", "closed", "resolved", "cancelled"]


class SectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    position: int


class PronoSummary(BaseModel):
    id: uuid.UUID
    kind: Kind
    question: str
    section: SectionOut
    state: PronoState
    base_gain: int
    opens_at: datetime | None
    closes_at: datetime | None
    open_ended: bool
    result_expected_at: datetime | None
    number_unit: str | None
    link_url: str | None
    image_url: str | None
    bet_count: int
    pot: int
    relaunch_count: int
    created_by: MemberPublic


class OptionOut(BaseModel):
    id: uuid.UUID
    label: str
    is_correct: bool | None
    count: int
    stake_total: int
    share_pct: int


class BucketOut(BaseModel):
    label: str
    count: int
    stake_total: int
    share_pct: int


class BetOut(BaseModel):
    id: uuid.UUID
    member: MemberPublic
    option_id: uuid.UUID | None
    number_value: Decimal | None
    date_value: date | None
    answer: str
    stake: int
    rank: int
    placed_at: datetime
    superseded: bool
    outcome: Literal["pending", "won", "lost", "refunded"]
    payout: int


class PronoEventOut(BaseModel):
    kind: str
    at: datetime
    data: dict[str, Any]


class WinnerOut(BaseModel):
    member: MemberPublic
    bet_id: uuid.UUID
    stake: int
    payout: int
    base_gain: int
    early_bird: int
    pot_share: int


class SpecialEditionOut(BaseModel):
    """The published result of a prono: who won what, and whether the pot was lost."""

    settlement_seq: int
    kind: Literal["resolution", "correction", "cancellation"]
    result: str | None
    settled_at: datetime
    pot: int
    pot_lost: bool
    winners: list[WinnerOut]


class PronoDetail(PronoSummary):
    options: list[OptionOut]
    distribution: list[BucketOut]
    bets: list[BetOut]
    my_bet: BetOut | None
    can_rebet: bool
    can_edit: bool
    reactions: dict[str, int]
    my_reactions: list[str]
    events: list[PronoEventOut]
    special_edition: SpecialEditionOut | None = None


class PronoList(BaseModel):
    items: list[PronoSummary]
    next_cursor: str | None


class PronoIn(BaseModel):
    kind: Kind
    question: Annotated[str, StringConstraints(max_length=500)]
    section_id: uuid.UUID
    options: list[Annotated[str, StringConstraints(max_length=200)]] = Field(
        default_factory=list, max_length=100
    )
    base_gain: int
    link_url: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] | None = None
    image_id: uuid.UUID | None = None
    opens_at: AwareDatetime | None = None
    closes_at: AwareDatetime | None = None
    open_ended: bool = False
    result_expected_at: AwareDatetime | None = None
    number_unit: Annotated[str, StringConstraints(strip_whitespace=True, max_length=20)] | None = (
        None
    )


class PronoPatch(BaseModel):
    kind: Kind | None = None
    question: Annotated[str, StringConstraints(max_length=500)] | None = None
    section_id: uuid.UUID | None = None
    options: list[Annotated[str, StringConstraints(max_length=200)]] | None = Field(
        default=None, max_length=100
    )
    base_gain: int | None = None
    link_url: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] | None = None
    image_id: uuid.UUID | None = None
    opens_at: AwareDatetime | None = None
    closes_at: AwareDatetime | None = None
    open_ended: bool | None = None
    result_expected_at: AwareDatetime | None = None
    number_unit: Annotated[str, StringConstraints(strip_whitespace=True, max_length=20)] | None = (
        None
    )


class BetIn(BaseModel):
    option_id: uuid.UUID | None = None
    number_value: Annotated[Decimal, Field(max_digits=14, decimal_places=2)] | None = None
    date_value: date | None = None
    stake: int = Field(ge=0)


class UploadOut(BaseModel):
    id: uuid.UUID
    width: int
    height: int


class ResultIn(BaseModel):
    """The correct options of a choice or yes/no prono, or the real number or date."""

    correct_option_ids: list[uuid.UUID] | None = Field(default=None, max_length=100)
    result_number: Annotated[Decimal, Field(max_digits=14, decimal_places=2)] | None = None
    result_date: date | None = None


Reason = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]


class RelaunchIn(BaseModel):
    closes_at: AwareDatetime
    result_expected_at: AwareDatetime | None = None
    reason: Reason | None = None


class CancelIn(BaseModel):
    reason: Reason | None = None


class ReportIn(BaseModel):
    kind: Literal["result_error", "content"]
    message: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] | None = None


class ReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    prono_id: uuid.UUID
    kind: Literal["result_error", "content"]
    message: str | None
    state: Literal["open", "resolved", "dismissed"]
    created_at: datetime
