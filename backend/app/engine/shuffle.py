"""The order in which a question's options are shown where no order is stored. Pure.

An exam attempt draws an order and stores it. A practice set stores none, so its order is derived
from a seed that names the set and the question: the same order on every reload, another one in
another set, and the correct option wherever chance puts it.
"""
import random


def option_order(keys: list[str], seed: str) -> list[str]:
    """The keys rearranged, the same way every time for the same seed."""
    return random.Random(seed).sample(keys, len(keys))
