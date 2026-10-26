"""Elo ability/difficulty updates (handover/05-algorithms.md §1–2). Pure functions."""
import math
from dataclasses import dataclass


@dataclass(frozen=True)
class EloUpdate:
    theta: float
    b: float
    p: float


def p_correct(theta: float, b: float) -> float:
    return 1.0 / (1.0 + math.exp(-(theta - b)))


def k_factor(k0: float, decay: float, n: int) -> float:
    return k0 / (1.0 + decay * n)


def update(theta: float, b: float, correct: bool, n_learner: int, n_item: int, cfg: dict) -> EloUpdate:
    p = p_correct(theta, b)
    delta = (1.0 if correct else 0.0) - p
    k_theta = k_factor(cfg["theta_k0"], cfg["theta_decay"], n_learner)
    k_b = k_factor(cfg["b_k0"], cfg["b_decay"], n_item)
    return EloUpdate(theta=theta + k_theta * delta, b=b - k_b * delta, p=p)


def mastery_of(theta: float) -> float:
    return p_correct(theta, 0.0)


def is_assessed(n_responses: int, min_responses: int) -> bool:
    return n_responses >= min_responses
