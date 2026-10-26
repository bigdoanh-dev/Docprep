import pytest

from app.config import env
from app.db import connect, migrate, truncate_all
from app.repo.learners import find_by_pseudonym
from seed import run_seed

def test_database_url() -> str:
    """The database the test session rebuilds. It must be named, and must not be the development one:
    with DATABASE_URL_TEST unset, connect() would fall back to DATABASE_URL and the session would drop it."""
    url = env("DATABASE_URL_TEST")
    if not url or url == env("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL_TEST must be set and differ from DATABASE_URL: "
                           "the test session drops and rebuilds that database's schema.")
    return url


test_database_url.__test__ = False  # a helper, not a test


@pytest.fixture(scope="session")
def migrated():
    """The test database, rebuilt from the migrations once per session."""
    url = test_database_url()
    with connect(url) as c:
        c.execute("drop schema if exists public cascade")
        c.execute("create schema public")
    migrate(url)


@pytest.fixture
def conn(migrated):
    """A connection to the migrated test database, every table empty."""
    c = connect(test_database_url())
    truncate_all(c)
    c.commit()
    yield c
    c.rollback()
    c.close()


@pytest.fixture
def learner(conn):
    """The seeded database (blueprint, demo content) and its dev learner."""
    run_seed(conn)
    return dev_learner(conn)


def dev_learner(conn) -> dict:
    """The learner the seed creates (config: learner.pseudonym)."""
    from app.config import settings

    return find_by_pseudonym(conn, settings()["learner"]["pseudonym"])


def correct_key(conn, qid: str) -> str:
    opts = conn.execute("select options from question where id=%s", (qid,)).fetchone()["options"]
    return next(o["key"] for o in opts if o["is_correct"])


def wrong_key(conn, qid: str) -> str:
    opts = conn.execute("select options from question where id=%s", (qid,)).fetchone()["options"]
    return next(o["key"] for o in opts if not o["is_correct"])


def glossary(conn) -> list[dict]:
    return conn.execute("select term, synonyms from glossary_term").fetchall()


# ---- app-level fixtures -------------------------------------------------------------------

from datetime import datetime, timedelta, timezone  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

from app.gateway import FakeGateway  # noqa: E402
from app.main import create_app  # noqa: E402


class Clock:
    def __init__(self):
        self.now = datetime(2026, 10, 10, 9, 0, tzinfo=timezone.utc)

    def advance(self, **kw):
        self.now += timedelta(**kw)

    def __call__(self):
        return self.now


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def fake_gw():
    """Scripted model. Tests set `fake_gw.responses = [...]`."""
    return FakeGateway([])


@pytest.fixture
def api(conn, clock, fake_gw):
    """The real /v1 API on the seeded test database, with the clock and the model under the test's control."""
    from app.api import deps as api_deps

    run_seed(conn)
    app = create_app("real", database_url=test_database_url())
    app.dependency_overrides[api_deps.get_now] = lambda: clock()
    app.dependency_overrides[api_deps.get_gateway] = lambda: fake_gw
    with TestClient(app) as c:
        yield c


def birth_dose_json(conn, hours: str = "24 giờ") -> str:
    """A well-formed model answer about the hepatitis B birth dose, fenced like real output."""
    text = conn.execute("select text from passage where id='tc-p02'").fetchone()["text"]
    start = text.index("Vắc xin viêm gan B mũi sơ sinh")
    quote = text[start:text.index(".", start)]
    assert "24 giờ" in quote
    claim = f"Vắc xin viêm gan B mũi sơ sinh được tiêm trong vòng {hours} đầu sau sinh."
    return ('```json\n{"evidence":[{"passage_id":"tc-p02","quote":"%s"}],'
            '"claims":[{"text":"%s","passage_ids":["tc-p02"]}]}\n```' % (quote, claim))


def sse_events(body: str) -> list[tuple[str, dict]]:
    import json
    out, event = [], None
    for line in body.splitlines():
        if line.startswith("event: "):
            event = line[7:]
        elif line.startswith("data: "):
            out.append((event, json.loads(line[6:])))
    return out


# ---- unit-flow helpers ----------------------------------------------------------------------

def _test_conn():
    return connect(env("DATABASE_URL_TEST"))


def walk_unit(client, unit_id: str, wrong: dict[str, str] | None = None) -> dict:
    """Go through a unit: quiz items get `wrong[item_id]` when given, else the correct key."""
    wrong = wrong or {}
    view = client.get(f"/v1/units/{unit_id}/next").json()
    while not view["done"]:
        item = view["item"]
        if item["kind"] == "quiz":
            with _test_conn() as c:
                chosen = wrong.get(item["unit_item_id"]) or correct_key(c, item["question"]["id"])
            r = client.post(f"/v1/units/{unit_id}/responses", json={"unit_item_id": item["unit_item_id"], "chosen": chosen})
            assert r.status_code == 200, r.text
        view = client.post(f"/v1/units/{unit_id}/advance", json={"unit_item_id": item["unit_item_id"]}).json()
    return view


def make_wrong_unit_answer(client) -> dict:
    """Open u-dt-01, pass the first content card, answer its first quiz with the wrong option "b"."""
    client.get("/v1/units/u-dt-01/next")
    client.post("/v1/units/u-dt-01/advance", json={"unit_item_id": "u1-c1"})
    return client.post("/v1/units/u-dt-01/responses", json={"unit_item_id": "u1-q1", "chosen": "b"}).json()


def answer_all(client, attempt: dict, wrong: int = 0, blank: int = 0) -> None:
    """Answer the first `wrong` questions incorrectly, leave the next `blank` empty, the rest correctly."""
    with _test_conn() as c:
        for i, q in enumerate(attempt["questions"]):
            if wrong <= i < wrong + blank:
                continue
            chosen = wrong_key(c, q["id"]) if i < wrong else correct_key(c, q["id"])
            r = client.put(f"/v1/attempts/{attempt['attempt_id']}/answers/{q['id']}",
                           json={"chosen": chosen, "flagged": False})
            assert r.status_code == 200, r.text


# ---- the /v1 API: clients and signed-in callers ---------------------------------------------

def bearer(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


def _issue(subject_type: str, subject_id: int, now) -> dict:
    """Headers carrying freshly issued tokens for that learner or staff member."""
    from app.services.auth import issue_tokens

    with _test_conn() as c:
        return bearer(issue_tokens(c, subject_type, subject_id, now).access_token)


def _give_service_consent(conn, learner_id: int, now) -> None:
    from app.config import settings

    conn.execute("insert into consent_record(learner_id, kind, version, given_at) values (%s, 'service', %s, %s)",
                 (learner_id, settings()["consent"]["version"], now))


def _add_staff(conn, role: str, n: int = 1) -> int:
    return conn.execute(
        "insert into staff_user(email, password_hash, display_name, role) values (%s, '!', %s, %s) returning id",
        (f"{role}-{n}@example.org", f"{role} {n}", role)).fetchone()["id"]


@pytest.fixture
def mock_app():
    return create_app("mock")


@pytest.fixture
def mock_client(mock_app):
    with TestClient(mock_app) as c:
        yield c


@pytest.fixture(scope="module")
def real_client(migrated):
    """Real mode on the test database, seeded once per module, with a signed-in caller of each role
    in `role_headers`. For checks that run once per operation and write nothing."""
    now = datetime.now(timezone.utc)
    with _test_conn() as c:
        truncate_all(c)
        run_seed(c)
        learner = dev_learner(c)
        _give_service_consent(c, learner["id"], now)
        staff = {role: _add_staff(c, role) for role in ("reviewer", "admin", "ministry_viewer")}
    headers = {"learner": _issue("learner", learner["id"], now)}
    headers.update({role: _issue("staff", staff_id, now) for role, staff_id in staff.items()})
    with TestClient(create_app("real", database_url=test_database_url())) as c:
        c.role_headers = headers
        yield c


COHORT_END = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)
COHORT_NOW = datetime(2026, 10, 13, 3, 0, tzinfo=timezone.utc)


@pytest.fixture(scope="module")
def cohort_api(migrated):
    """Real mode on a small sample cohort (20 learners, two weeks ending 05/10/2026), seeded once per
    module, the clock at 13/10/2026, with a signed-in caller of each role in `role_headers`."""
    from app.api import deps as api_deps
    from seed import cohort

    with _test_conn() as c:
        truncate_all(c)
        run_seed(c)
        cohort.run(c, learners=20, weeks=2, seed=7, end=COHORT_END)
        staff = {role: _add_staff(c, role) for role in ("reviewer", "admin", "ministry_viewer")}
        learner = dev_learner(c)
        _give_service_consent(c, learner["id"], COHORT_NOW)
    headers = {"learner": _issue("learner", learner["id"], COHORT_NOW)}
    headers.update({role: _issue("staff", staff_id, COHORT_NOW) for role, staff_id in staff.items()})
    app = create_app("real", database_url=test_database_url())
    app.dependency_overrides[api_deps.get_now] = lambda: COHORT_NOW
    with TestClient(app) as client:
        client.role_headers = headers
        client.staff_ids = staff
        yield client


@pytest.fixture
def learner_headers(api, learner, clock):
    """The seeded dev learner, signed in, with no consent given."""
    return _issue("learner", learner["id"], clock())


@pytest.fixture
def consented_headers(api, conn, learner, clock):
    """The seeded dev learner, signed in, with the current service consent."""
    _give_service_consent(conn, learner["id"], clock())
    conn.commit()
    return _issue("learner", learner["id"], clock())


@pytest.fixture
def learner_api(api, consented_headers):
    """The /v1 client signed in as the consented dev learner: every request carries their token
    unless the call passes other headers."""
    api.headers.update(consented_headers)
    return api


@pytest.fixture
def tokens_for_new_learner(api, conn, clock):
    """A function: headers of another learner, newly created, with the current service consent."""
    from app.repo import learners

    def make() -> dict:
        learner_id = learners.create(conn, learners.next_pseudonym(conn), None, "student", "2027-03-15", 0.9,
                                     "Người học khác")
        _give_service_consent(conn, learner_id, clock())
        conn.commit()
        return _issue("learner", learner_id, clock())

    return make


@pytest.fixture
def staff_headers(api, conn, clock):
    """A function: role -> headers of a new staff member of that role."""
    made = []

    def make(role: str) -> dict:
        made.append(role)
        staff_id = _add_staff(conn, role, len(made))
        conn.commit()
        return _issue("staff", staff_id, clock())

    return make
