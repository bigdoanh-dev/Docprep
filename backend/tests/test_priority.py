from app.engine.priority import TopicState, rank_topics


def T(code, weight, module, mastery):
    return TopicState(code, code, weight, module, mastery)


def test_focus_module_first():
    ts = [T("A", 0.9, "other", None), T("B", 0.1, "focus", 0.9)]
    assert rank_topics(ts, ["focus"], 0.5) == ["B", "A"]


def test_unassessed_scored_with_neutral():
    ts = [T("A", 0.2, "m", None), T("B", 0.2, "m", 0.9), T("C", 0.2, "m", 0.1)]
    assert rank_topics(ts, ["m"], 0.5) == ["C", "A", "B"]


def test_higher_weight_wins_at_equal_mastery():
    ts = [T("A", 0.1, "m", 0.4), T("B", 0.3, "m", 0.4)]
    assert rank_topics(ts, ["m"], 0.5) == ["B", "A"]


def test_ranking_is_stable_on_ties():
    ts = [T("B", 0.2, "m", None), T("A", 0.2, "m", None)]
    assert rank_topics(ts, ["m"], 0.5) == rank_topics(list(reversed(ts)), ["m"], 0.5) == ["A", "B"]
