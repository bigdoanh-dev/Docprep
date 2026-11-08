"""Classification and assessment counts from the exact question versions answered.

The bank stores three grouped Bloom bands, not the six individual Bloom levels.
Unanswered questions are not assessments; empty groups remain unassessed.
"""
LEVELS = {1: "Nhớ, Hiểu", 2: "Vận dụng", 3: "Phân tích, Đánh giá"}


def _catalog(conn):
    modules = conn.execute("select id, name, short_name, competency_codes, core_issue_group_id from module order by ord").fetchall()
    issues = conn.execute("select id, group_id, name from core_issue order by id").fetchall()
    return modules, issues


def classification(conn, question: dict) -> dict:
    modules, issues = _catalog(conn)
    module = next((m for m in modules if question["competency_code"] in m["competency_codes"]), None)
    issue = next((i for i in issues if i["id"] == question["core_issue_id"]), None)
    return {
        "module_id": module["id"] if module else None,
        "module_name": module["short_name"] if module else None,
        "core_issue_id": question["core_issue_id"],
        "core_issue_name": issue["name"] if issue else None,
        "difficulty_label": question["difficulty_label"],
        "bloom_level": question["bloom_level"],
        "bloom_label": LEVELS[question["bloom_level"]],
    }


def form_scope(conn, form: dict) -> dict:
    """A fixed single-module form has that scope. Assembly spans the whole bank."""
    modules, _ = _catalog(conn)
    questions = conn.execute(
        "select distinct id, competency_code from question where id = any(%s) and status = 'approved'",
        (form["question_ids"],)).fetchall() if form["kind"] != "assembled" else []
    matched = [next((m for m in modules if q["competency_code"] in m["competency_codes"]), None) for q in questions]
    module = matched[0] if matched and all(m and m["id"] == matched[0]["id"] for m in matched) else None
    if len(questions) != len(form["question_ids"]):
        module = None
    return {"module_id": module["id"] if module else None,
            "module_name": module["short_name"] if module else None}


def summary(conn, learner_id: int, attempt_ids: list[int]) -> dict:
    modules, issues = _catalog(conn)

    def levels():
        return [{"level": n, "label_vi": label, "correct": 0, "total": 0} for n, label in LEVELS.items()]

    overall = levels()
    specialties = [{"module_id": m["id"], "name": m["short_name"], "correct": 0, "total": 0} for m in modules]
    bloom = [{"module_id": m["id"], "name": m["short_name"], "levels": levels()} for m in modules]
    by_issue = [{"module_id": m["id"], "name": m["short_name"], "issues": [
        {"issue_id": i["id"], "name": i["name"], "correct": 0, "total": 0}
        for i in issues if i["group_id"] == m["core_issue_group_id"]]} for m in modules]
    module_of = {}
    for index, module in enumerate(modules):
        for code in module["competency_codes"]:
            module_of.setdefault(code, index)
    issue_counts = {i["issue_id"]: i for group in by_issue for i in group["issues"]}
    rows = conn.execute(
        """select q.competency_code, q.core_issue_id, q.bloom_level,
                  count(*) as total, count(*) filter (where r.correct) as correct
           from item_response r join question q on q.id = r.question_id and q.version = r.question_version
           where r.learner_id = %s and r.attempt_id = any(%s)
           group by q.competency_code, q.core_issue_id, q.bloom_level""", (learner_id, attempt_ids))
    for row in rows:
        targets = [overall[row["bloom_level"] - 1]]
        index = module_of.get(row["competency_code"])
        if index is not None:
            targets += [specialties[index], bloom[index]["levels"][row["bloom_level"] - 1]]
        if row["core_issue_id"] in issue_counts:
            targets.append(issue_counts[row["core_issue_id"]])
        for target in targets:
            for key in ("correct", "total"):
                target[key] += row[key]
    return {"levels": overall, "specialties": specialties, "bloom_by_specialty": bloom,
            "issues_by_specialty": by_issue}
