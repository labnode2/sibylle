"""Who may do what inside a newsroom: the rights matrix of the spec."""

from enum import StrEnum


class Role(StrEnum):
    READER = "reader"  # lecteur·rice
    JOURNALIST = "journalist"  # journaliste
    EDITOR = "editor"  # rédaction en chef


class Action(StrEnum):
    BET = "bet"
    REACT = "react"
    VIEW_CHOICES = "view_choices"
    REPORT = "report"
    PROPOSE_PRONO = "propose_prono"
    PUBLISH_PRONO = "publish_prono"
    VALIDATE_PROPOSAL = "validate_proposal"
    EDIT_PRONO = "edit_prono"
    DESIGNATE_RESULT = "designate_result"
    RELAUNCH_PRONO = "relaunch_prono"
    CREATE_PUZZLE = "create_puzzle"
    MANAGE_MEMBERS = "manage_members"
    CUSTOMIZE_CARD = "customize_card"
    SET_LAURELS = "set_laurels"
    MANAGE_SECTIONS = "manage_sections"
    CORRECT_RESULT = "correct_result"
    CANCEL_PRONO = "cancel_prono"
    ADJUST_LAURELS = "adjust_laurels"
    HANDLE_REPORTS = "handle_reports"
    SCHEDULE_GAMES = "schedule_games"


_EVERYONE = frozenset(Role)
_NEWSROOM = frozenset({Role.JOURNALIST, Role.EDITOR})
_EDITOR = frozenset({Role.EDITOR})

_ALLOWED: dict[Action, frozenset[Role]] = {
    Action.BET: _EVERYONE,
    Action.REACT: _EVERYONE,
    Action.VIEW_CHOICES: _EVERYONE,
    Action.REPORT: _EVERYONE,
    # Journalists publish directly, so only readers go through a proposal.
    Action.PROPOSE_PRONO: frozenset({Role.READER}),
    Action.PUBLISH_PRONO: _NEWSROOM,
    Action.VALIDATE_PROPOSAL: _NEWSROOM,
    Action.EDIT_PRONO: _NEWSROOM,
    Action.DESIGNATE_RESULT: _NEWSROOM,
    Action.RELAUNCH_PRONO: _NEWSROOM,
    Action.CREATE_PUZZLE: _NEWSROOM,
    Action.MANAGE_MEMBERS: _EDITOR,
    Action.CUSTOMIZE_CARD: _EDITOR,
    Action.SET_LAURELS: _EDITOR,
    Action.MANAGE_SECTIONS: _EDITOR,
    Action.CORRECT_RESULT: _EDITOR,
    Action.CANCEL_PRONO: _EDITOR,
    Action.ADJUST_LAURELS: _EDITOR,
    Action.HANDLE_REPORTS: _EDITOR,
    Action.SCHEDULE_GAMES: _EDITOR,
}


def can(role: Role | str, action: Action) -> bool:
    return Role(role) in _ALLOWED[action]
