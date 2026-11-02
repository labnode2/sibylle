import pytest

from sybille.domain.permissions import Action, Role, can

pytestmark = pytest.mark.unit

READER, JOURNALIST, EDITOR = Role.READER, Role.JOURNALIST, Role.EDITOR

# The rights matrix of the spec (« Rôles et droits »), plus the reports and Pixel mystère puzzles.
MATRIX: dict[Action, set[Role]] = {
    Action.BET: {READER, JOURNALIST, EDITOR},
    Action.REACT: {READER, JOURNALIST, EDITOR},
    Action.VIEW_CHOICES: {READER, JOURNALIST, EDITOR},
    Action.REPORT: {READER, JOURNALIST, EDITOR},
    Action.PROPOSE_PRONO: {READER},
    Action.PUBLISH_PRONO: {JOURNALIST, EDITOR},
    Action.VALIDATE_PROPOSAL: {JOURNALIST, EDITOR},
    Action.EDIT_PRONO: {JOURNALIST, EDITOR},
    Action.DESIGNATE_RESULT: {JOURNALIST, EDITOR},
    Action.RELAUNCH_PRONO: {JOURNALIST, EDITOR},
    Action.CREATE_PUZZLE: {JOURNALIST, EDITOR},
    Action.MANAGE_MEMBERS: {EDITOR},
    Action.CUSTOMIZE_CARD: {EDITOR},
    Action.SET_LAURELS: {EDITOR},
    Action.MANAGE_SECTIONS: {EDITOR},
    Action.CORRECT_RESULT: {EDITOR},
    Action.CANCEL_PRONO: {EDITOR},
    Action.ADJUST_LAURELS: {EDITOR},
    Action.HANDLE_REPORTS: {EDITOR},
}


def test_matrix_covers_every_action() -> None:
    assert set(MATRIX) == set(Action)


@pytest.mark.parametrize("action", list(Action))
@pytest.mark.parametrize("role", list(Role))
def test_rights_matrix(role: Role, action: Action) -> None:
    assert can(role, action) is (role in MATRIX[action])


def test_roles_are_stored_as_their_values() -> None:
    assert [role.value for role in Role] == ["reader", "journalist", "editor"]
