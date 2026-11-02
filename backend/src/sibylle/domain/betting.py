"""What makes a prono well-formed, and when a bet is accepted (spec FR-030 to FR-044)."""

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from sibylle.domain.lifecycle import State


class Kind(StrEnum):
    CHOICE = "choice"
    YES_NO = "yes_no"
    NUMBER = "number"
    DATE = "date"


YES_NO_OPTIONS = ["Oui", "Non"]
MAX_NUMBER = Decimal("1e12")


class ValidationFailed(ValueError):
    def __init__(self, fields: dict[str, str]) -> None:
        super().__init__(", ".join(f"{k}: {v}" for k, v in fields.items()))
        self.fields = fields


@dataclass
class PronoDraft:
    kind: Kind
    question: str
    base_gain: int
    options: list[str] = field(default_factory=list)
    link_url: str | None = None
    opens_at: datetime | None = None
    closes_at: datetime | None = None
    open_ended: bool = False
    result_expected_at: datetime | None = None


def validate_prono(draft: PronoDraft, *, max_base_gain: int, now: datetime) -> list[str]:
    """Checks a prono before it is published or edited; returns its options."""
    errors: dict[str, str] = {}
    question = draft.question.strip()
    if not 5 <= len(question) <= 200:
        errors["question"] = "length"
    if draft.link_url and not (
        draft.link_url.startswith("https://") and len(draft.link_url) <= 500
    ):
        errors["link_url"] = "https_only"
    if not 0 <= draft.base_gain <= max_base_gain:
        errors["base_gain"] = "out_of_range"

    if draft.open_ended:
        if draft.kind != Kind.DATE:
            errors["open_ended"] = "date_only"
        if draft.closes_at is not None:
            errors["closes_at"] = "open_ended"
    elif draft.closes_at is None:
        errors["closes_at"] = "missing"
    elif draft.closes_at <= now:
        errors["closes_at"] = "past"

    if draft.opens_at is not None and draft.closes_at is not None:
        if draft.opens_at >= draft.closes_at:
            errors["opens_at"] = "after_closing"
    if draft.result_expected_at is not None and draft.closes_at is not None:
        if draft.result_expected_at < draft.closes_at:
            errors["result_expected_at"] = "before_closing"

    options = [option.strip() for option in draft.options]
    if draft.kind == Kind.CHOICE:
        if (
            len(options) < 2
            or any(not 1 <= len(option) <= 80 for option in options)
            or len({option.lower() for option in options}) != len(options)
        ):
            errors["options"] = "invalid"
    elif draft.kind == Kind.YES_NO:
        options = list(YES_NO_OPTIONS)
    elif options:
        errors["options"] = "not_allowed"

    if errors:
        raise ValidationFailed(errors)
    return options


@dataclass(frozen=True)
class Answer:
    option_id: object | None = None
    number_value: Decimal | None = None
    date_value: date | None = None


class BetRefused(Exception):
    def __init__(self, code: str, fields: dict[str, str] | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.fields = fields or {}


def _check_answer(kind: Kind, answer: Answer, *, open_ended: bool, today: date) -> None:
    given = {
        "option_id": answer.option_id is not None,
        "number_value": answer.number_value is not None,
        "date_value": answer.date_value is not None,
    }
    expected = {
        Kind.CHOICE: "option_id",
        Kind.YES_NO: "option_id",
        Kind.NUMBER: "number_value",
        Kind.DATE: "date_value",
    }[kind]
    if not given[expected] or sum(given.values()) != 1:
        raise BetRefused("validation_error", {expected: "missing"})
    if answer.number_value is not None:
        value = answer.number_value
        exponent = value.as_tuple().exponent
        if (
            not value.is_finite()
            or abs(value) >= MAX_NUMBER
            or (isinstance(exponent, int) and exponent < -2)
        ):
            raise BetRefused("validation_error", {"number_value": "invalid"})
    if answer.date_value is not None and open_ended and answer.date_value <= today:
        # An open-ended date is a bet on the future: strictly after the day of the bet.
        raise BetRefused("validation_error", {"date_value": "not_future"})


def check_bet(
    *,
    state: State,
    kind: Kind,
    open_ended: bool,
    closes_at: datetime | None,
    now: datetime,
    today: date,
    balance: int,
    stake: int,
    answer: Answer,
    has_active_bet: bool,
    active_bet_date: date | None,
) -> None:
    """Raises BetRefused unless the bet can be placed. `today` is the day in Paris."""
    if State(state) is not State.OPEN or (closes_at is not None and now >= closes_at):
        raise BetRefused("invalid_state")
    if stake < 0:
        raise BetRefused("validation_error", {"stake": "negative"})
    if stake > 0 and stake > balance:
        # With a negative balance (after a correction) only a bet without stake is possible.
        raise BetRefused("insufficient_balance")
    if has_active_bet:
        passed = open_ended and active_bet_date is not None and active_bet_date < today
        if not passed:
            raise BetRefused("already_bet")
    _check_answer(Kind(kind), answer, open_ended=open_ended, today=today)


@dataclass(frozen=True)
class Bucket:
    label: str
    count: int
    stake_total: int


def _label(value: Decimal | date) -> str:
    if isinstance(value, date):
        return value.isoformat()
    return format(value.normalize(), "f")


def distribution(values: list[tuple[Decimal | date, int]], buckets: int = 6) -> list[Bucket]:
    """Number and date bets grouped for display: one bucket per value when there are few,
    otherwise `buckets` equal ranges. Each value comes with its stake."""
    if not values:
        return []
    distinct = sorted({value for value, _ in values})
    if len(distinct) <= buckets:
        return [
            Bucket(
                _label(v),
                sum(1 for value, _ in values if value == v),
                sum(stake for value, stake in values if value == v),
            )
            for v in distinct
        ]
    as_numbers = [
        (Decimal(value.toordinal()) if isinstance(value, date) else value, stake)
        for value, stake in values
    ]
    low = min(v for v, _ in as_numbers)
    high = max(v for v, _ in as_numbers)
    width = (high - low) / buckets
    result = []
    for i in range(buckets):
        start = low + width * i
        end = low + width * (i + 1)
        inside = [
            (v, s) for v, s in as_numbers if start <= v < end or (i == buckets - 1 and v == high)
        ]

        def show(x: Decimal) -> str:
            if isinstance(values[0][0], date):
                return date.fromordinal(int(x)).isoformat()
            return format(x.quantize(Decimal("0.01")).normalize(), "f")

        result.append(
            Bucket(f"{show(start)} – {show(end)}", len(inside), sum(s for _, s in inside))
        )
    return result
