"""Thiếu bằng chứng: the answer says where the system looked, and the nearest chapter when there is one."""
import re

from app.chat.normalise import normalise
from app.chat.retrieval import find
from app.config import settings
from app.repo import content
from app.schemas.chat import ChatMessageList, NearestChapter, SearchedSource
from tests.conftest import sse_events

NOTHING = "Phác đồ hoá trị ung thư phổi giai đoạn III?"
Q = "Vắc xin viêm gan B mũi sơ sinh tiêm khi nào?"


def ask(client, text, **session):
    sid = client.post("/v1/chat/sessions", json=session).json()["id"]
    r = client.post(f"/v1/chat/sessions/{sid}/messages", json={"text": text})
    assert r.status_code == 200, r.text
    return sid, sse_events(r.text)


def found(conn, text, module_id=None):
    cfg = settings()["retrieval"]
    return find(conn, normalise(text, content.glossary(conn)), cfg["top_k"], cfg["min_score"], module_id)


def test_nothing_found_lists_every_document_it_looked_in(learner_api, conn, fake_gw):
    sid, events = ask(learner_api, NOTHING)
    final = events[-1][1]
    titles = [r["title"] for r in conn.execute("select title from document order by title")]
    assert final["state"] == "insufficient_evidence" and [s["document"] for s in final["searched"]] == titles
    for source in final["searched"]:
        SearchedSource.model_validate(source)
        assert re.fullmatch(r"tr\. \d+(–\d+)?|toàn văn", source["range"]), source
    pages = conn.execute("select min(p.page_start) a, max(p.page_start) b from passage p join document d on d.id = p.document_id "
                         "where d.title = %s", (titles[0],)).fetchone()
    assert final["searched"][0]["range"] == (f"tr. {pages['a']}–{pages['b']}" if pages["a"] != pages["b"] else f"tr. {pages['a']}")
    assert conn.execute("select searched from chat_message where role = 'assistant'").fetchone()["searched"] == final["searched"]
    body = learner_api.get(f"/v1/chat/sessions/{sid}/messages").json()
    ChatMessageList.model_validate(body)
    assert body["items"][1]["searched"] == final["searched"] and fake_gw.calls == []


def test_a_search_limited_to_a_hoc_phan_lists_only_its_documents(learner_api, conn):
    _sid, events = ask(learner_api, NOTHING, module_id="g1")
    inside = [r["title"] for r in conn.execute(
        """select distinct d.title from passage p join document d on d.id = p.document_id
           where p.competency_code = any(select unnest(competency_codes) from module where id = 'g1') order by d.title""")]
    everything = conn.execute("select count(*) c from document").fetchone()["c"]
    assert [s["document"] for s in events[-1][1]["searched"]] == inside and 0 < len(inside) <= everything


def test_the_nearest_chapter_is_offered_only_when_something_came_near(learner_api, conn):
    near = "Sơ sinh phác đồ hoá trị ung thư phổi giai đoạn muộn di căn xương"       # shares a few words, far below the threshold
    nearest = found(conn, near).nearest
    assert found(conn, near).passages == [] and nearest is not None
    _sid, events = ask(learner_api, near)
    final = events[-1][1]
    NearestChapter.model_validate(final["nearest_chapter"])
    assert final["nearest_chapter"]["passage_id"] == nearest.id
    assert final["nearest_chapter"]["label_vi"] == (f"{nearest.document_title} · {nearest.chapter}" if nearest.chapter else nearest.document_title)
    assert conn.execute("select nearest_chapter from chat_message where role = 'assistant'").fetchone()["nearest_chapter"] == final["nearest_chapter"]

    far = "Xyzzy qwertyuiop"                                                        # shares nothing with any passage
    assert found(conn, far).nearest is None
    _sid, events = ask(learner_api, far)
    assert events[-1][1]["state"] == "insufficient_evidence" and events[-1][1]["nearest_chapter"] is None
    assert events[-1][1]["searched"]                                                # it still says where it looked


def test_an_answer_the_model_could_not_support_lists_what_it_read(learner_api, conn, fake_gw):
    fake_gw.responses = ['{"insufficient": true}']
    _sid, events = ask(learner_api, Q)
    final = events[-1][1]
    read = found(conn, Q).passages
    assert final["state"] == "insufficient_evidence" and final["nearest_chapter"] is None
    assert [s["document"] for s in final["searched"]] == list(dict.fromkeys(p.document_title for p in read))
    first = [p for p in read if p.document_title == final["searched"][0]["document"]]
    assert final["searched"][0]["range"] == "tr. " + ", ".join(dict.fromkeys(str(p.page_start) for p in first))


def test_an_answer_never_carries_where_it_searched(learner_api, conn, fake_gw):
    from tests.conftest import birth_dose_json
    fake_gw.responses = [birth_dose_json(conn)]
    _sid, events = ask(learner_api, Q)
    assert events[-1][1]["state"] == "answered" and events[-1][1]["searched"] == [] and events[-1][1]["nearest_chapter"] is None
