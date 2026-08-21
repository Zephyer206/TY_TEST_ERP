from types import SimpleNamespace

from app.api.parts import _select_primary_twp, _select_primary_tooling


def test_twp_primary_is_explicit_and_unambiguous():
    first = SimpleNamespace(id=1, is_primary=False)
    second = SimpleNamespace(id=2, is_primary=True)
    assert _select_primary_twp([first, second]) is second

    assert _select_primary_twp([first]) is None
    assert _select_primary_twp([
        SimpleNamespace(id=3, is_primary=True),
        SimpleNamespace(id=4, is_primary=True),
    ]) is None


def test_continuous_tooling_always_wins_primary_display_selection():
    simple = SimpleNamespace(is_continuous=False, tooling_number="TY-Q0001", id=1)
    continuous = SimpleNamespace(is_continuous=True, tooling_number="TY-Q0002", id=2)
    records = [
        (SimpleNamespace(is_primary=True), simple),
        (SimpleNamespace(is_primary=False), continuous),
    ]
    assert _select_primary_tooling(records)[1] is continuous

