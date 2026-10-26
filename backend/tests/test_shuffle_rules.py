"""The order of a question's options where no order is stored: pure, the same every time for the same seed."""
from app.engine.shuffle import option_order

KEYS = ["a", "b", "c", "d"]


def test_the_order_is_a_rearrangement_and_never_changes_for_a_seed():
    order = option_order(KEYS, "31:q-dt-02")
    assert sorted(order) == KEYS and order == option_order(KEYS, "31:q-dt-02")
    assert option_order([], "x") == [] and option_order(["a"], "x") == ["a"]
    assert KEYS == ["a", "b", "c", "d"]                                    # the caller's list is left alone


def test_the_first_option_is_not_always_the_authored_first():
    orders = [option_order(KEYS, f"{set_id}:q-dt-02") for set_id in range(1, 81)]
    first = sum(order[0] == "a" for order in orders)
    assert 8 <= first <= 32                                                # about a quarter of 80, not most of them
    assert len({tuple(order) for order in orders}) > 12                    # many different orders, not a couple
