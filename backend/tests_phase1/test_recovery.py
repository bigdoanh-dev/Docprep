"""Fault injection against real PostgreSQL/Redis; no external model is contacted."""
import multiprocessing
import os
import signal
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from types import SimpleNamespace
import pytest
from app.db import connect, open_pool
from app.repo import turns, chat
from app.chat.worker import ChatWorker, utcnow
from app.chat.admission import Admission
from app.phase_config import PhaseConfig
from app.services import chat as chat_service
from app.api.turns import _submit
from .test_runtime import ask, parse, wait


def enqueue(world, text="Vắc xin viêm gan B mũi sơ sinh tiêm khi nào?", key=None, cfg=None):
    _, (c, _), _, url = world
    with connect(url) as conn:
        learner = conn.execute("select * from learner limit 1").fetchone()
        sid = chat.create_session(conn, learner['pseudonym_id'], utcnow())
        body = {"text": text, "detail": False, "session_id": sid}
        return turns.submit(conn, cfg or c.app.state.phase_config, learner['id'], 'chat', '/chat',
            key or uuid.uuid4().hex, body, body, utcnow(),
            lambda: chat_service.begin_turn(conn, learner, sid, text, False, utcnow())['id'])


def stop_claims(world):
    for client in world[1]: client.app.state.worker.draining = True
    time.sleep(.4)


def killed_worker(url, cfg, stage, ready, started):
    """Pause a real child worker at each irreversible invocation/commit boundary."""
    from app.gateway import FakeGateway
    pool = open_pool(url, 1, 4)
    model_returned = threading.Event()
    class Controlled(ChatWorker):
        def prepare(self, conn, turn, learner):
            if stage == 'before_call':
                ready.set(); time.sleep(30)
            return super().prepare(conn, turn, learner)
        def check(self, turn):
            if stage == 'before_result_commit' and model_returned.is_set():
                ready.set(); time.sleep(30)
            return super().check(turn)
    class ControlledAdmission(Admission):
        def emit(self, turn_id, event, data):
            if stage == 'after_result_commit' and event == 'answer':
                ready.set(); time.sleep(30)
            return super().emit(turn_id, event, data)
    def model(task, messages):
        if stage == 'inside_call':
            ready.set(); time.sleep(30)
        model_returned.set()
        return '{"insufficient":true}'
    worker = Controlled(pool, ControlledAdmission(cfg), cfg, lambda: FakeGateway(model))
    worker.start()
    started.set()
    while True: time.sleep(1)


@pytest.mark.parametrize('stage', ['before_call','inside_call','before_result_commit','after_result_commit'])
def test_kill_worker_recovers_each_commit_window(world, stage):
    stop_claims(world)
    b, clients, _, url = world
    cfg = clients[0].app.state.phase_config
    context = multiprocessing.get_context('spawn')
    ready = context.Event()
    started = context.Event()
    process = context.Process(target=killed_worker, args=(url, cfg, stage, ready, started))
    process.start()
    try:
        # Startup/import cost is independent of the dispatch deadline, especially
        # when a regression suite shares the development machine's CPU.
        assert started.wait(20)
        turn = enqueue(world)
        assert ready.wait(10)
        process.kill(); process.join(5)
        assert not process.is_alive()
        def reconciled():
            with connect(url) as conn:
                current = turns.get(conn, turn['id'])
                return current if current['status'] != 'running' else None
        current = wait(reconciled, 10)
        if stage == 'before_call':
            assert current['status'] == 'queued'
            clients[1].app.state.worker.draining = False
            wait(lambda: clients[1].get(f"/v1/chat/turns/{turn['id']}").json()['turn_status'] == 'completed')
        elif stage == 'after_result_commit':
            assert current['status'] == 'completed'
            # The result committed, but no answer/final was published before the kill.
            response = clients[1].get(f"/v1/chat/turns/{turn['id']}/events")
            pairs = parse(response)
            assert sum(name == 'answer' for name, _ in pairs) == 1
            assert pairs[-1][1]['turn_status'] == 'completed'
            with connect(url) as conn:
                assert conn.execute('select count(*) n from chat_message where ai_turn_id=%s', (turn['id'],)).fetchone()['n'] == 1
                assert conn.execute('select count(*) n from ai_model_call where turn_id=%s', (turn['id'],)).fetchone()['n'] == 1
        elif stage == 'inside_call':
            assert current['status'] == 'interrupted'
            with connect(url) as conn:
                calls = conn.execute('select * from ai_model_call where ended_at is null').fetchall()
                assert len(calls) == 1 and calls[0]['quarantined']
                assert conn.execute('select count(*) n from chat_message where ai_turn_id=%s', (turn['id'],)).fetchone()['n'] == 0
            assert clients[0].app.state.admission.r.hlen(clients[0].app.state.admission.key('slots:scripted')) == 1
        else:
            assert current['status'] == 'interrupted'
            with connect(url) as conn:
                calls = conn.execute('select * from ai_model_call where turn_id=%s', (turn['id'],)).fetchall()
                assert len(calls) == 1 and calls[0]['ended_at'] is not None
                assert conn.execute('select count(*) n from chat_message where ai_turn_id=%s', (turn['id'],)).fetchone()['n'] == 0
    finally:
        if process.is_alive(): process.kill(); process.join(5)


def test_queue_capacity_timeout_and_failed_admission_is_atomic(world):
    from dataclasses import replace
    stop_claims(world)
    _, (c, _), _, url = world
    cfg = replace(c.app.state.phase_config, waiting=1)
    turn = enqueue(world, cfg=cfg)
    with connect(url) as conn:
        from app.repo.learners import create
        from app.repo.consent import give
        other = create(conn, 'HV-CAPACITY', None, 'student', '2027-03-15', .9, 'Test')
        from app.config import settings
        give(conn, other, 'service', settings()['consent']['version'], utcnow())
    with connect(url) as conn:
        from app.errors import ApiError
        with pytest.raises(ApiError) as caught:
            turns.submit(conn, cfg, other, 'chat','/chat','full',{}, {},utcnow(), lambda: pytest.fail('must not begin'))
        assert caught.value.code == 'ai_queue_full'
    with connect(url) as conn:
        conn.execute("update ai_turn set queue_deadline=now()-interval '1 second' where id=%s", (turn['id'],))
    wait(lambda: c.get(f"/v1/chat/turns/{turn['id']}").json()['turn_status'] == 'failed')


def test_shared_fifo_dispatch_and_slot_cap(world):
    from dataclasses import replace
    stop_claims(world)
    original = world[1][0].app.state.admission
    cfg = replace(original.cfg, active=1, model_limit=1, namespace=original.cfg.namespace + ':atomic')
    from app.chat.admission import Admission
    bounded = Admission(cfg)
    coord = bounded
    epoch = bounded.reset()
    bounded.r.set(bounded.key('ready'), epoch)
    try:
        # Atomic dispatch tests use separate IDs and prove both workers share the same cap.
        for seq in (3,1,2):
            bounded.enqueue({'id':str(seq), 'seq':seq, 'learner_id':seq+100})
        assert bounded.claim(epoch, time.time()) == '1'
        assert bounded.claim(epoch, time.time()) is None
        second = Admission(cfg)
        assert second.claim(epoch, time.time()) is None
        coord.release({'id':'1','learner_id':101})
        assert second.claim(epoch, time.time()) == '2'
        coord.release({'id':'2','learner_id':102})
        second.close()
        assert bounded.claim(epoch, time.time()) == '3'
        a, b = uuid.uuid4(), uuid.uuid4()
        assert bounded.slot('scripted', a, 'worker-a')
        assert not bounded.slot('scripted', b, 'worker-b')
        bounded.release_slot('scripted', a)
        assert bounded.slot('scripted', b, 'worker-b')
    finally:
        bounded.close()


@pytest.mark.parametrize('action', ['exam','consent','delete'])
def test_lifecycle_during_model_call_cannot_publish_answer(world, action):
    b, (c1,c2), fake, url = world
    entered, release = threading.Event(), threading.Event()
    def blocked(task, messages):
        entered.set(); assert release.wait(10); return '{"insufficient":true}'
    fake.responses = blocked
    with ThreadPoolExecutor(1) as executor:
        running = executor.submit(ask,c1)
        assert entered.wait(5)
        tid = c2.get('/v1/chat/turns/active').json()['item']['turn_id']
        try:
            if action == 'exam':
                form = b.get('/v1/exams').json()['items'][0]['id']
                assert b.post(f'/v1/exams/{form}/attempts',json={}).status_code == 200
            elif action == 'consent': assert b.delete('/v1/consent?kind=service').status_code == 200
            else: assert b.delete('/v1/me').status_code == 200
        finally: release.set()
        response = running.result(8)
        assert not any(name == 'answer' for name,_ in parse(response))
        with connect(url) as conn:
            assert conn.execute('select count(*) n from chat_message where ai_turn_id=%s',(tid,)).fetchone()['n'] == 0


def test_hint_releases_request_pool_during_model_wait(world):
    b, (c1,c2), fake, url = world
    entered, release = threading.Event(), threading.Event()
    b.get('/v1/units/u-dt-01/next')
    b.post('/v1/units/u-dt-01/advance',json={'unit_item_id':'u1-c1'})
    def blocked(task,messages):
        entered.set(); assert release.wait(8); return '{"hint":"Hãy đọc kỹ khái niệm trong tài liệu."}'
    fake.responses=blocked
    with ThreadPoolExecutor(1) as executor:
        response = executor.submit(c1.post,'/v1/items/q-dt-01/hint',headers={'Idempotency-Key':'hint'})
        assert entered.wait(5)
        try:
            assert c1.app.state.pool.get_stats()['pool_available'] >= c1.app.state.pool.get_stats()['pool_size']-1
            assert c2.get('/v1/chat/turns/active').json()['item']['kind'] == 'hint'
        finally: release.set()
        assert response.result().status_code == 200


def test_lost_lease_and_late_fenced_result_cannot_commit(world):
    _, (c1, c2), fake, url = world
    entered, release = threading.Event(), threading.Event()
    def blocked(task, messages):
        entered.set()
        assert release.wait(12)
        return '{"insufficient":true}'
    fake.responses = blocked
    with ThreadPoolExecutor(1) as executor:
        response = executor.submit(ask, c1)
        assert entered.wait(5)
        tid = c2.get('/v1/chat/turns/active').json()['item']['turn_id']
        try:
            with connect(url) as conn:
                # Simulate a superseded owner whose model call has not acknowledged cancellation.
                conn.execute("update ai_turn set owner='superseded',fence=fence+1,heartbeat_at=now()-interval '1 minute' where id=%s", (tid,))
            wait(lambda: c2.get(f'/v1/chat/turns/{tid}').json()['turn_status'] == 'interrupted')
            with connect(url) as conn:
                assert conn.execute('select quarantined from ai_model_call where turn_id=%s and ended_at is null', (tid,)).fetchone()['quarantined']
        finally:
            release.set()
        assert parse(response.result(8))[-1][1]['turn_status'] == 'interrupted'
        def released():
            with connect(url) as conn:
                return conn.execute('select count(*) n from ai_model_call where turn_id=%s and ended_at is null', (tid,)).fetchone()['n'] == 0
        wait(released)
        with connect(url) as conn:
            assert conn.execute('select count(*) n from chat_message where ai_turn_id=%s', (tid,)).fetchone()['n'] == 0
        assert len(fake.calls) == 1


def test_stale_worker_cannot_release_replacement_dispatch_lease(world):
    stop_claims(world)
    # Freeze the periodic reconciler so it cannot conceal an incorrect release.
    for client in world[1]:
        client.app.state.worker.stop.set()
        client.app.state.worker.thread.join(5)
    worker = world[1][0].app.state.worker
    turn = enqueue(world)
    old = {**turn, 'owner': worker.owner, 'fence': 1, 'status': 'running'}
    with connect(world[3]) as conn:
        conn.execute("update ai_turn set status='running',owner='replacement',fence=2,heartbeat_at=now() where id=%s", (turn['id'],))
    worker.reconcile()
    key = worker.coord.key('processing')
    before = worker.coord.r.zscore(key, str(turn['id']))
    assert before is not None
    worker.run(old)
    assert worker.coord.r.zscore(key, str(turn['id'])) == before
    with connect(world[3]) as conn:
        current = turns.get(conn, turn['id'])
        assert current['status'] == 'running' and current['fence'] == 2
    assert not world[2].calls
