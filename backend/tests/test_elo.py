import pytest

from app.engine.elo import is_assessed, k_factor, mastery_of, p_correct, update

CFG = {"theta_k0": 0.8, "theta_decay": 0.1, "b_k0": 0.4, "b_decay": 0.05}


def test_p_correct_symmetric():
    assert p_correct(0, 0) == pytest.approx(0.5)
    assert p_correct(1, 0) == pytest.approx(1 - p_correct(-1, 0))


def test_correct_raises_theta_lowers_b():
    u = update(0.0, 0.0, True, 0, 0, CFG)
    assert u.theta == pytest.approx(0.4) and u.b == pytest.approx(-0.2) and u.p == pytest.approx(0.5)


def test_wrong_lowers_theta_raises_b():
    u = update(0.0, 0.0, False, 0, 0, CFG)
    assert u.theta < 0 < u.b


def test_k_shrinks_with_responses():
    assert k_factor(0.8, 0.1, 10) == pytest.approx(0.4)


def test_mastery_is_probability_on_average_item():
    assert mastery_of(0.0) == pytest.approx(0.5) and mastery_of(2.0) > 0.85


def test_assessed_threshold():
    assert not is_assessed(2, 3) and is_assessed(3, 3)
