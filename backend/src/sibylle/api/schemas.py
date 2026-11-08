"""Request and response bodies (contracts/rest-api.md). Responses never carry a member's name,
first name or e-mail, except `Me`, which is the account's own."""

import uuid
from collections.abc import Iterable
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal, Self

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)
from pydantic_core import PydanticCustomError

from sibylle import clock
from sibylle.db.models import Account, Membership, Organisation
from sibylle.domain.coins import gold
from sibylle.domain.game_schedule import GAMES, Game
from sibylle.domain.notifications import allowed_push_endpoint
from sibylle.domain.seasons import edition_number

EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

Email = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=254, pattern=EMAIL_PATTERN)
]
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
    logo: PixelImage
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
    animation: str | None = None
    role: Role
    joined_at: datetime

    @classmethod
    def of(cls, member: Membership) -> Self:
        return cls.model_validate(member, from_attributes=True)


class MemberListed(MemberPublic):
    """A member in the newsroom's list, with their chain of wins under way (US13) and their green
    laurels, which their press card shows too (the editor adjusts them from this list)."""

    streak: int
    balance: int


class MemberSelf(MemberPublic):
    # Green laurels: what the member can stake.
    balance: int
    # Gold laurels: the balance plus the stakes in play; each Monday turns them into coins.
    gold: int
    season_score: int
    coins: int
    unlocked_colors: list[int] = []
    # The press card seen without an account (US15), and the token of its address
    # (/carte/<token>), drawn the first time it goes public and kept afterwards.
    card_public: bool = False
    card_token: str | None = None

    @classmethod
    def build(cls, member: Membership, *, in_play: int, unlocked: Iterable[int] = ()) -> Self:
        return cls(
            **MemberPublic.of(member).model_dump(),
            balance=member.balance,
            gold=gold(member.balance, in_play),
            season_score=member.season_score,
            coins=member.coins,
            unlocked_colors=sorted(unlocked),
            card_public=member.card_public,
            card_token=member.card_token,
        )


class MembershipEntry(BaseModel):
    org: OrgCard
    membership: MemberSelf
    # The newsroom's open pronos the member has not bet on yet: a badge in the newsroom lists.
    unanswered: int = 0
    # The newsroom's only editor while others stay: they name another one before leaving or
    # deleting their account (`last_editor`).
    sole_editor: bool = False


class Me(BaseModel):
    id: uuid.UUID
    email: str
    first_name: str
    last_name: str
    email_verified: bool
    theme: Theme
    reduce_motion: bool
    locale: str
    # The welcome pop-up that explains the game has been closed.
    welcomed: bool
    memberships: list[MembershipEntry]

    @classmethod
    def of(
        cls,
        account: Account,
        memberships: list[tuple[Organisation, Membership]],
        in_play: dict[uuid.UUID, int],
        unanswered: dict[uuid.UUID, int],
        sole_editors: set[uuid.UUID],
    ) -> Self:
        return cls(
            id=account.id,
            email=account.email or "",
            first_name=account.first_name or "",
            last_name=account.last_name or "",
            email_verified=account.email_verified_at is not None,
            theme=account.theme,
            reduce_motion=account.reduce_motion,
            locale=account.locale,
            welcomed=account.welcomed_at is not None,
            memberships=[
                MembershipEntry(
                    org=OrgCard.of(org),
                    membership=MemberSelf.build(member, in_play=in_play.get(member.id, 0)),
                    unanswered=unanswered.get(member.id, 0),
                    sole_editor=member.id in sole_editors,
                )
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
    # « N° 305 »: the day of the newsroom's life, its first day being N° 1 (Paris time).
    edition_number: int
    my_membership: MemberSelf

    @classmethod
    def build(
        cls,
        org: Organisation,
        me: Membership,
        member_count: int,
        *,
        in_play: int,
        unlocked: Iterable[int] = (),
    ) -> Self:
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
            edition_number=edition_number(org.created_at, clock.now()),
            my_membership=MemberSelf.build(me, in_play=in_play, unlocked=unlocked),
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


class MePatch(BaseModel):
    """The account's own settings. Names and e-mail change in Keycloak, which Sibylle copies at
    each sign-in (specs/002-keycloak-auth/contracts/auth.md)."""

    theme: Theme | None = None
    reduce_motion: bool | None = None
    locale: Literal["fr"] | None = None
    # The welcome pop-up has been closed; it does not come back.
    welcomed: Literal[True] | None = None


class AccountDeletion(BaseModel):
    confirm: Literal[True]


class OrgIn(BaseModel):
    title: Title
    background_key: str
    # Without one, the newsroom takes the default logo.
    logo: PixelImage | None = None
    pseudo: Pseudo
    avatar: PixelImage


class ShowcaseRef(BaseModel):
    """An object of the member's collection, or one of their engraved trophies."""

    kind: Literal["item", "trophy"]
    id: uuid.UUID


class MemberPatch(BaseModel):
    pseudo: Pseudo | None = None
    avatar: PixelImage | None = None
    # A frame of the member's collection; null takes the frame off.
    avatar_frame_item_id: uuid.UUID | None = None
    # An animation of the member's collection around the avatar; null takes it off.
    avatar_animation_item_id: uuid.UUID | None = None
    # What the press card shows, in order: three at most; an empty list shows nothing.
    showcase: list[ShowcaseRef] | None = Field(default=None, max_length=3)
    # The press card seen by anyone with its link, without an account (US15).
    card_public: bool | None = None


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
    # « PRONO N° 128 »: its number in the newsroom.
    number: int
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
    # The messages of its discussion (US14).
    message_count: int
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
    # « VALIDÉ PAR INÈS »: who designated the result, corrected it or cancelled the prono.
    settled_by: MemberPublic
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
    # Why a journalist turned the proposal down; its author sees it.
    rejected_reason: str | None = None
    my_reports: list[ReportOut] = []
    events: list[PronoEventOut]
    special_edition: SpecialEditionOut | None = None


class PronoList(BaseModel):
    items: list[PronoSummary]
    next_cursor: str | None


# The discussion of a prono (US14)


class MessageIn(BaseModel):
    # 1 to 500 characters once the spaces around are gone; the service says which is wrong.
    body: Annotated[str, StringConstraints(max_length=2000)]


class MessageOut(BaseModel):
    id: uuid.UUID
    author: MemberPublic
    body: str
    created_at: datetime
    likes: int
    # Whether the member reading likes it, and the pseudos of who does, in the order they did.
    liked: bool
    likers: list[str]
    # For its author and the editor.
    can_delete: bool


class MessagePage(BaseModel):
    # Oldest first; `has_more` when older ones are left.
    items: list[MessageOut]
    has_more: bool


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


class ValidateIn(BaseModel):
    # The proposal's own gain when left out.
    base_gain: int | None = Field(default=None, ge=0)


class RejectIn(BaseModel):
    reason: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] | None = None


ReactionKind = Literal["jackpot", "yes", "enfin", "serieux", "malaise"]


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
    handled_at: datetime | None = None
    # The editor's note to the author when handling it.
    resolution_note: str | None = None


class PronoRef(BaseModel):
    id: uuid.UUID
    question: str


class ReportDetail(ReportOut):
    """A report as the editor sees it, with its prono and its author."""

    prono: PronoRef
    reporter: MemberPublic


class HandleIn(BaseModel):
    state: Literal["resolved", "dismissed"]
    note: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] | None = None


class LeaderboardRow(BaseModel):
    rank: int
    member: MemberPublic
    value: int
    is_me: bool
    # The member's chain of wins under way, whatever the period (US13).
    streak: int


class Leaderboard(BaseModel):
    # "2026-11" (month), "2026-autumn" (season) or "all_time"; the interface words it.
    period_label: str
    rows: list[LeaderboardRow]


class SeasonOut(BaseModel):
    year: int
    name: Literal["spring", "summer", "autumn", "winter"]
    starts_at: datetime
    ends_at: datetime


class FrontProno(PronoSummary):
    """A prono of la une, with the split of the answers its gauge draws."""

    options: list[OptionOut]
    distribution: list[BucketOut]


class LatestResult(BaseModel):
    prono: PronoSummary
    result: str | None
    resolved_at: datetime | None
    # The member's own bet, when they played.
    my_outcome: Literal["pending", "won", "lost", "refunded"] | None
    my_payout: int | None


class FrontPage(BaseModel):
    """La une, its blocks in the spec's order."""

    headline: FrontProno | None
    open: list[FrontProno]
    # Every open prono the member sees, the headline included.
    open_count: int
    # Journalists and the editor only; None for a reader.
    to_designate: list[PronoSummary] | None
    latest_results: list[LatestResult]
    # The month's first five, then the member's own line when they are not among them.
    leaderboard_top: list[LeaderboardRow]
    # "2026-11": the month of that ranking.
    leaderboard_period: str
    editor_note: str | None


# The editor's settings (US6)

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5000)]


class OrgPatch(BaseModel):
    title: Title | None = None
    logo: PixelImage | None = None
    background_key: str | None = None
    starting_balance: int | None = Field(default=None, ge=0)
    max_base_gain: int | None = Field(default=None, ge=0)
    early_bird_pct: int | None = Field(default=None, ge=0, le=100)
    early_bird_count: int | None = Field(default=None, ge=0)
    editor_note: Annotated[str, StringConstraints(max_length=500)] | None = None
    charter: Text | None = None

    @model_validator(mode="after")
    def _no_null_settings(self) -> Self:
        """Only the logo and the note can be removed (a removed logo gives way to the default
        one); the other settings always have a value."""
        for name in self.model_fields_set - {"logo", "editor_note"}:
            if getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self


class AccessCodeOut(BaseModel):
    access_code: str


class RoleIn(BaseModel):
    role: Role


class AdjustmentIn(BaseModel):
    amount: int
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]

    @model_validator(mode="after")
    def _not_zero(self) -> Self:
        if self.amount == 0:
            raise ValueError("an adjustment cannot be zero")
        return self


class LedgerEntryOut(BaseModel):
    id: int
    kind: str
    amount: int
    score_delta: int
    reason: str | None
    prono: PronoRef | None
    created_at: datetime


class LedgerPage(BaseModel):
    items: list[LedgerEntryOut]
    next_cursor: str | None


SectionName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]


class SectionIn(BaseModel):
    name: SectionName


class SectionPatch(BaseModel):
    name: SectionName | None = None
    position: int | None = Field(default=None, ge=0)


# The collection and the press card (US7)


class CatalogItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: Literal["ball", "color", "frame", "animation"]
    key: str
    name_key: str
    price: int | None
    season: str | None
    # A ball's kit variant, a colour's palette index and hex, a frame's or an animation's style.
    data: dict[str, Any]


class CatalogEntry(BaseModel):
    item: CatalogItemOut
    # This week's price: the deal's for the object on sale, else its usual price.
    price: int | None
    # Only for the deal of the week (research.md J10): its usual price, the share off, and next
    # Monday 00:00 in Paris, when it ends.
    regular_price: int | None = None
    discount_pct: int | None = None
    discount_until: datetime | None = None
    owned: bool


class PurchaseIn(BaseModel):
    # The price the screen showed: refused with price_changed if it is no longer this week's.
    price: int | None = None


class OwnedItemOut(BaseModel):
    item: CatalogItemOut
    source: Literal["purchase", "secret_code"]
    acquired_at: datetime


class PurchaseOut(BaseModel):
    owned_item: OwnedItemOut
    coins: int


class WeeklyCoins(BaseModel):
    """Monday's conversion: the gold laurels of that moment and the coins they became."""

    model_config = ConfigDict(from_attributes=True)

    week_start: date
    gold: int
    amount: int


class WeeklySeenIn(BaseModel):
    week_start: date


class RedeemIn(BaseModel):
    code: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]


class RedeemOut(BaseModel):
    item: CatalogItemOut


class SeasonRef(BaseModel):
    year: int
    name: Literal["spring", "summer", "autumn", "winter"]


class TrophyOut(BaseModel):
    id: uuid.UUID
    season: SeasonRef
    score: int
    rank: int
    podium: bool


class PressStats(BaseModel):
    # The green laurels: the balance, what the member can stake, as their date bar shows it.
    laurels: int
    pronos_played: int
    settled: int
    wins: int
    # Won out of settled, in percent; None before a first result.
    success_rate: int | None
    # Pronos won in a row up to the latest result, and the longest such chain (US13).
    streak: int
    best_streak: int


class ShowcaseOut(BaseModel):
    kind: Literal["item", "trophy"]
    item: CatalogItemOut | None = None
    trophy: TrophyOut | None = None

    @classmethod
    def of(cls, entry: dict[str, Any]) -> Self:
        return cls(
            kind=entry["kind"],
            item=CatalogItemOut.model_validate(entry["item"]) if "item" in entry else None,
            trophy=TrophyOut.model_validate(entry["trophy"]) if "trophy" in entry else None,
        )


class PressCard(MemberPublic):
    """A member's press card, as every member of the newsroom sees it."""

    card_number: str
    stats: PressStats
    trophies: list[TrophyOut]
    collection: list[OwnedItemOut]
    # Up to three objects or trophies the member chose to show.
    showcase: list[ShowcaseOut]


class PublicNewsroom(BaseModel):
    title: str
    logo: PixelImage


class PublicCard(BaseModel):
    """A press card its member made public (US15), for anyone, without an account: the card
    itself and its figures. Neither the member's id, nor their statement, bets or messages."""

    newsroom: PublicNewsroom
    pseudo: str
    avatar: PixelImage
    frame: str | None
    animation: str | None = None
    role: Role
    joined_at: datetime
    card_number: str
    stats: PressStats
    showcase: list[ShowcaseOut]


# Notifications (US8)

NotificationKind = Literal["new_prono", "closing_soon", "result", "designation_reminder"]
NotificationChannel = Literal["push", "email"]


class NotificationPrefItem(BaseModel):
    type: NotificationKind
    channel: NotificationChannel
    enabled: bool


class VapidKey(BaseModel):
    """The server's public key for `pushManager.subscribe`; null when push is not set up."""

    key: str | None


def _push_service(endpoint: str) -> str:
    if not allowed_push_endpoint(endpoint):
        raise PydanticCustomError("unknown_push_service", "not a browser push service")
    return endpoint


class PushKeys(BaseModel):
    p256dh: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    auth: Annotated[str, StringConstraints(min_length=1, max_length=100)]


class PushSubscriptionIn(BaseModel):
    """What `PushSubscription.toJSON()` gives in the browser."""

    endpoint: Annotated[str, StringConstraints(max_length=2048), AfterValidator(_push_service)]
    keys: PushKeys


class PushSubscriptionOut(BaseModel):
    id: uuid.UUID


# Mini-games (US9, US10)


class RunnerTopRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    member: MemberPublic
    score: int
    rank: int


class RunnerStatus(BaseModel):
    week_start: date
    attempts_left: int
    my_best: int | None
    top: list[RunnerTopRow]


class PixelFindOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    member: MemberPublic
    rank: int


class PixelStatus(BaseModel):
    """`revealed`: the drawing in base64, one byte per pixel, 255 for a pixel not shown yet; the
    whole drawing and `word` once the member found it, drew it, or the game ended."""

    puzzle_id: uuid.UUID
    size: Literal[16, 32]
    revealed: str
    revealed_count: int
    letters: int
    guesses_left_today: int
    finds: list[PixelFindOut]
    found_by_me: bool
    mine: bool
    state: Literal["active", "finished"]
    word: str | None


class Games(BaseModel):
    """The current week's games (`scheduled`), and each one's state: `runner` is null when the
    race is not on; out of the week's games, `pixel` is only the last drawing once finished."""

    scheduled: list[Game]
    runner: RunnerStatus | None
    pixel: PixelStatus | None


class GamesIn(BaseModel):
    """Games for a week; their order and repeats do not matter."""

    games: list[Game] = Field(max_length=len(GAMES))


class GameWeekOut(BaseModel):
    week_start: date
    games: list[Game]
    planned: bool


class GameSchedule(BaseModel):
    """`default`: the games of an ordinary week, from next week on. `weeks`: the current week and
    the three after it; `planned` when a week has games of its own."""

    default: list[Game]
    weeks: list[GameWeekOut]


class PixelPuzzleIn(BaseModel):
    drawing: PixelImage
    word: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]


class PixelQueueItem(BaseModel):
    """A drawing to come or in play; its word and drawing only for its author."""

    puzzle_id: uuid.UUID
    state: Literal["active", "queued"]
    size: Literal[16, 32]
    letters: int
    mine: bool
    word: str | None
    drawing: PixelImage | None
    created_at: datetime


class PixelGuessIn(BaseModel):
    word: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]


class PixelGuessOut(BaseModel):
    correct: bool
    rank: int | None
    laurels: int | None
    guesses_left_today: int


class RunStarted(BaseModel):
    run_id: uuid.UUID
    seed: int


class RunFinishIn(BaseModel):
    score: int = Field(ge=0, le=1_000_000)
    duration_ms: int = Field(ge=0, le=86_400_000)


class RunFinished(BaseModel):
    score: int
    my_best: int
    rank: int | None
