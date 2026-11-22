"""Learner-adapted teaching: what the layout stage should do for this learner, decided in code.

Version 2 (2026-11-23, after the reviewer's points): the learner is described by a Bloom profile on
the competencies the passages cover, not by one mastery number, and a weak topic is met with
scaffolding, not with simpler words.

- Bloom profile: the share of correct answers at each of the six levels (revised taxonomy) on those
  competencies. The highest level held with every lower observed level held is `secure`; the first
  observed level not held is the `frontier` the answer teaches toward. Each frontier has its own way
  of explaining (FRONTIER_MOVES): facts for Remember, meaning for Understand, ordered steps with
  conditions for Apply, distinctions and relations for Analyse, criteria and priorities for Evaluate.
- Scaffolding (Wood, Bruner & Ross 1976; fading as the learner rises):
  * prerequisite bridge: when the frontier is at Apply or below and a prerequisite competency
    (competency_node.prerequisite_codes) is weak in the mastery table, one or two passages of that
    prerequisite are given to the layout stage, which may add a grounding sentence from them;
  * misconceptions: the learner's own recent wrong answers on those competencies, with the bank's
    rationale for why the chosen option is wrong, so the answer can name the confusion and state
    what the guideline says instead (counter-evidence; the sentence must quote a passage);
  * a closing self-check question at the frontier level, answerable from the verified claims.
  The more the learner holds, the less of this is used.
- Plain wording is never chosen from a low profile: low mastery is missing knowledge, not reading.
  Simpler words come only when the learner taps "Tôi chưa hiểu" (pipeline mode don_gian).

The model never sees numbers about the learner or anything that identifies them, only what to do,
plus the wording of their earlier wrong option. The block is used only by the layout stage
(app/chat/adapt.py), after the grounded answer has been written and checked, and a policy never
removes a claim. Labels behind it (six-level Bloom, the prerequisite map) are machine-made and
unreviewed for now (migration 0021): a reviewed bloom_level_6 always wins.
"""
from dataclasses import dataclass, field, replace

from app.chat.normalise import Normalised
from app.chat.retrieval import Passage, find
from app.config import settings
from app.engine.elo import mastery_of
from app.repo import consent

BLOOM_VI = {1: "Nhớ", 2: "Hiểu", 3: "Vận dụng", 4: "Phân tích", 5: "Đánh giá", 6: "Sáng tạo"}
# The bank's grouped bands, when no six-level label exists: the lowest level each band stands for.
BAND_TO_LEVEL = {1: 2, 2: 3, 3: 4}
FRONTIER_MOVES = {
    1: "Nêu rõ khái niệm, sự kiện hoặc con số cốt lõi trước, đúng thuật ngữ, rồi mới tới chi tiết.",
    2: "Sau ý trả lời trực tiếp, nói rõ ý nghĩa: vì sao, cơ chế, hoặc điều đó có nghĩa gì trong thực hành.",
    3: "Sắp xếp các ý theo thứ tự các bước thực hiện, và nói rõ điều kiện hoặc khi nào áp dụng từng bước.",
    4: "Làm rõ quan hệ và cách phân biệt: dấu hiệu nào phân biệt các trường hợp, yếu tố nào dẫn tới yếu tố nào.",
    5: "Đưa tiêu chí, ngưỡng và thứ tự ưu tiên để ra quyết định lên trước, và nói vì sao chọn như vậy.",
    6: "Cô đọng; gom các ý thành một quy trình hoặc kế hoạch hoàn chỉnh theo đúng tài liệu.",
}


@dataclass(frozen=True)
class Misconception:
    stem: str          # the question the learner got wrong
    chosen: str        # the option they chose
    why_wrong: str     # the bank's rationale for that option
    correct: str       # the key


@dataclass(frozen=True)
class Signals:
    rungs: dict[int, tuple[int, int]]          # Bloom level -> (answers, correct), on these competencies
    weak_prerequisites: tuple[tuple[str, str], ...] = ()   # (code, name) of weak prerequisite competencies
    misconceptions: tuple[Misconception, ...] = ()

    @property
    def n_responses(self) -> int:
        return sum(n for n, _ in self.rungs.values())


@dataclass(frozen=True)
class Policy:
    secure: int                    # highest Bloom level held; 0: none yet
    frontier: int                  # the level to teach toward (1–6)
    scaffold: bool                 # False: Bloom wording only (the experiments' ablation)
    additions: int                 # sentences beyond the verified claims, each stated by a passage
    prerequisites: tuple[tuple[str, str], ...] = ()
    misconceptions: tuple[Misconception, ...] = ()
    check_question: bool = False
    bridge: tuple[Passage, ...] = field(default=())   # passages of the weak prerequisites

    @property
    def level(self) -> str:        # for traces and experiments
        return f"bloom{self.secure}->{self.frontier}"


def cfg() -> dict:
    return settings()["personalization"]


def profile(rungs: dict[int, tuple[int, int]], c: dict) -> tuple[int, int] | None:
    """(secure, frontier) from the answers per level, or None when too little is known."""
    observed = sorted(lvl for lvl, (n, _) in rungs.items() if n >= c["min_level_items"])
    if not observed:
        return None
    secure = 0
    for lvl in observed:
        n, ok = rungs[lvl]
        if ok / n < c["pass_accuracy"]:
            return secure, lvl
        secure = lvl
    return secure, min(secure + 1, 6)


def policy_for(s: Signals, c: dict | None = None, *, scaffold: bool | None = None) -> Policy | None:
    """The fixed rules. None means: not enough known about this learner, answer as for anyone."""
    c = c or cfg()
    if s.n_responses < c["min_responses"]:
        return None
    got = profile(s.rungs, c)
    if got is None:
        return None
    secure, frontier = got
    scaffold = c["scaffolding"] if scaffold is None else scaffold
    additions = c["additions_by_frontier"][frontier]
    if not scaffold:
        return Policy(secure, frontier, False, additions)
    # Fading: prerequisites only while the topic itself is still at Apply or below.
    prereqs = s.weak_prerequisites if frontier <= 3 else ()
    mistakes = s.misconceptions[:c["max_misconceptions"]]
    return Policy(secure, frontier, True, additions + len(prereqs[:1]) + len(mistakes), prereqs, mistakes,
                  check_question=frontier <= 5)


def profile_text(p: Policy) -> str:
    """The instruction block for the layout stage: what to do, never data about the learner."""
    held = f"đã vững đến mức {BLOOM_VI[p.secure]}" if p.secure else "chưa vững mức nào"
    lines = ["Hồ sơ người học (chỉ để chọn cách giảng, không phải nguồn kiến thức):",
             f"- Theo thang Bloom ở chủ đề này, người học {held}; câu trả lời giảng hướng tới mức "
             f"{BLOOM_VI[p.frontier]}.",
             "- Luôn giữ ý trả lời trực tiếp câu hỏi trước; các quy tắc dưới đây chỉ đổi thứ tự, cách giảng "
             "và phần bổ sung, không bao giờ bỏ ý nào. Dùng đúng thuật ngữ chuyên môn; không viết lại cho "
             "đơn giản hơn chỉ vì người học còn yếu.",
             f"- Cách giảng: {FRONTIER_MOVES[p.frontier]}"]
    if p.bridge:
        names = ", ".join(name for _, name in p.prerequisites)
        ids = ", ".join(b.id for b in p.bridge)
        lines.append(f"- Người học còn yếu kiến thức nền: {names}. Ngay sau ý trả lời trực tiếp, thêm một câu "
                     f"nền tảng lấy từ đoạn [{ids}] để nối kiến thức nền với câu hỏi.")
    for m in p.misconceptions:
        lines.append(f"- Người học từng chọn sai \"{m.chosen}\" ở câu \"{m.stem}\" (đáp án đúng: \"{m.correct}\"; "
                     f"vì sao sai: {m.why_wrong}). Nếu chỗ nhầm này liên quan tới câu hỏi và một đoạn tài liệu nêu "
                     "điều đúng, thêm một câu chỉ ra chỗ dễ nhầm và điều tài liệu nói.")
    if p.check_question:
        lines.append(f"- Kết thúc bằng đúng một câu hỏi tự kiểm tra ở mức {BLOOM_VI[p.frontier]}, trả lời được "
                     "từ các ý đã kiểm chứng: \"kind\": \"check\", ghi số các ý đó vào \"claims\".")
    if p.additions:
        lines.append(f"- Được thêm tối đa {p.additions} câu bổ sung chỉ khi đoạn tài liệu viết đúng điều đó. "
                     "Không tự nghĩ ra ví dụ.")
    else:
        lines.append("- Không thêm câu bổ sung.")
    return "\n".join(lines) + "\n\n"


# ---- reading the learner's records (Business owns them; Chat has SELECT only) ----------------------

def _rungs(conn, learner_id: int, codes: list[str]) -> dict[int, tuple[int, int]]:
    rows = conn.execute(
        """select coalesce(q.bloom_level_6, l.level,
                           case q.bloom_level when 1 then %s when 2 then %s else %s end) as lvl,
                  count(*) as n, count(*) filter (where r.correct) as ok
           from item_response r
           join question q on q.id = r.question_id and q.version = r.question_version
           left join question_bloom_label l on l.question_id = q.id and l.question_version = q.version
           where r.learner_id = %s and q.competency_code = any(%s)
           group by 1""", (BAND_TO_LEVEL[1], BAND_TO_LEVEL[2], BAND_TO_LEVEL[3], learner_id, codes)).fetchall()
    return {r["lvl"]: (r["n"], r["ok"]) for r in rows}


def _weak_prerequisites(conn, learner_id: int, codes: list[str], c: dict) -> tuple[tuple[str, str], ...]:
    rows = conn.execute(
        """select distinct p.code, p.name, m.theta, m.n_responses
           from competency_node n join competency_node p on p.code = any(n.prerequisite_codes)
           left join mastery m on m.competency_code = p.code and m.learner_id = %s
           where n.code = any(%s) and not (p.code = any(%s)) order by p.code""", (learner_id, codes, codes)).fetchall()
    return tuple((r["code"], r["name"]) for r in rows
                 if r["theta"] is not None and r["n_responses"] >= c["min_responses"]
                 and mastery_of(r["theta"]) < c["weak_mastery"])


def _misconceptions(conn, learner_id: int, codes: list[str], c: dict) -> tuple[Misconception, ...]:
    rows = conn.execute(
        """select q.stem, q.options, r.chosen from item_response r
           join question q on q.id = r.question_id and q.version = r.question_version
           where r.learner_id = %s and not r.correct and r.chosen is not null and q.competency_code = any(%s)
             and not q.is_synthetic
           order by r.created_at desc limit %s""", (learner_id, codes, c["max_misconceptions"] * 3)).fetchall()
    out, seen = [], set()
    for r in rows:
        opts = {o.get("key"): o for o in r["options"] or []}
        chosen, key = opts.get(r["chosen"]), next((o for o in opts.values() if o.get("is_correct")), None)
        if not chosen or not key or not chosen.get("rationale") or r["stem"] in seen:
            continue
        seen.add(r["stem"])
        out.append(Misconception(r["stem"], chosen["text"], chosen["rationale"], key["text"]))
    return tuple(out[:c["max_misconceptions"]])


def signals(conn, learner_id: int, codes: list[str]) -> Signals:
    c = cfg()
    if not codes:
        return Signals({})
    return Signals(_rungs(conn, learner_id, codes), _weak_prerequisites(conn, learner_id, codes, c),
                   _misconceptions(conn, learner_id, codes, c))


def with_bridge(conn, policy: Policy | None, query: Normalised) -> Policy | None:
    """The passages of the weak prerequisites that best match the question, for the bridge sentence."""
    if policy is None or not policy.prerequisites:
        return policy
    c = cfg()
    found = find(conn, query, c["bridge_passages"], 0.0, competency_codes=[code for code, _ in policy.prerequisites])
    if not found.passages:
        return replace(policy, prerequisites=(), additions=max(policy.additions - 1, 0))
    return replace(policy, bridge=tuple(found.passages))


def for_turn(conn, learner_id: int | None, codes: list[str], query: Normalised | None = None) -> Policy | None:
    """The policy for this turn, or None: switched off, no consent, or too little known."""
    if learner_id is None or not cfg()["enabled"] or consent.active(conn, learner_id, "personalization") is None:
        return None
    policy = policy_for(signals(conn, learner_id, codes))
    return with_bridge(conn, policy, query) if query is not None else policy
