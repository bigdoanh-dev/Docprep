"""Boundary tests for the port, never requiring or contacting the real model server."""
from dataclasses import replace
from datetime import datetime, timezone, timedelta
import json
import threading
from concurrent.futures import ThreadPoolExecutor
import httpx
import pytest
from app.gateway import GatewayError
from app.ollama_gateway import OllamaConfig, OllamaGateway, ModelCallUncertain
from app.db import connect
from app.repo import embeddings, turns
from app.api.deps import get_gateway
from app.config import settings
from app.chat.worker import utcnow
from .test_runtime import ask, parse, wait

CFG = OllamaConfig('http://model.invalid:11434','qwen3.5:9b-q4_K_M','bge-m3',16384,2)


def model(handler=None):
    calls=[]
    def handle(request):
        if request.url.path == '/api/tags':
            return httpx.Response(200,json={'models':[{'name':n,'digest':'test-revision'} for n in (CFG.generator,CFG.embedding)]})
        body=json.loads(request.content); calls.append((request.url.path,body))
        if handler: return handler(request,body)
        if request.url.path == '/api/embed':
            return httpx.Response(200,json={'embeddings':[[3.,4.,0.] for _ in body['input']]})
        return httpx.Response(200,json={'done':True,'message':{'content':'{"insufficient":true}'},'prompt_eval_count':2,'eval_count':3})
    return OllamaGateway(CFG,transport=httpx.MockTransport(handle)),calls


def test_ollama_wire_payload_metadata_and_normalised_embeddings():
    gateway,calls=model()
    answer=gateway.complete('answer','system',[{'role':'user','content':'question'}],'answer-v1')
    assert answer.cost is None and answer.model == CFG.generator+'@test-revision'
    assert answer.tokens_in==2 and answer.tokens_out==3 and not answer.from_cache
    body=calls[0][1]
    assert body['stream'] is False and body['think'] is False and body['format']=='json'
    assert body['options']=={'temperature':.2,'num_ctx':16384}
    result=gateway.embed(['source'])
    assert result.vectors==[[.6,.8,0.]] and result.model=='bge-m3'
    assert calls[1][0]=='/api/embed'
    assert calls[1][1]['model']=='bge-m3'
    assert calls[1][1]['truncate'] is False
    with pytest.raises(GatewayError,match='role_not_configured'):
        gateway.complete('check','s',[],'check-v1')
    with pytest.raises(GatewayError):gateway.embed(['a@example.org'])
    with pytest.raises(GatewayError):gateway.complete('answer','s',[{'role':'user','content':'at_private'}],'v1')
    assert len(calls)==2


@pytest.mark.parametrize('kind',['read_timeout','write_error','unexpected','server_error','bad_json','no_done'])
def test_unacknowledged_calls_are_uncertain_and_never_retried(kind):
    def fail(request,body):
        if kind=='read_timeout':raise httpx.ReadTimeout('sensitive provider detail',request=request)
        if kind=='write_error':raise httpx.WriteError('sensitive provider detail',request=request)
        if kind=='unexpected':raise RuntimeError('sensitive provider detail')
        if kind=='server_error':return httpx.Response(500,text='sensitive provider detail')
        if kind=='bad_json':return httpx.Response(200,text='{')
        return httpx.Response(200,json={'message':{'content':'partial'}})
    gateway,calls=model(fail)
    with pytest.raises(ModelCallUncertain) as error:
        gateway.complete('answer','s',[],'v1')
    assert 'sensitive' not in str(error.value) and len(calls)==1


@pytest.mark.parametrize('status',[400,401,403,404,422,429])
def test_rejected_calls_are_acknowledged_errors(status):
    gateway,calls=model(lambda request,body:httpx.Response(status,text='private content'))
    with pytest.raises(GatewayError) as error:gateway.complete('hint','s',[],'v1')
    assert not isinstance(error.value,ModelCallUncertain) and len(calls)==1
    assert 'private' not in str(error.value)


def test_connection_failure_and_expired_deadline_do_not_dispatch_again():
    def fail(request,body):raise httpx.ConnectError('private',request=request)
    gateway,calls=model(fail)
    with pytest.raises(GatewayError) as error:gateway.complete('answer','s',[],'v1')
    assert not isinstance(error.value,ModelCallUncertain)
    with pytest.raises(GatewayError):gateway.complete('answer','s',[],'v1',deadline=utcnow()-timedelta(seconds=1))
    assert len(calls)==1


def test_chat_only_config_does_not_export_environment(tmp_path,monkeypatch):
    import os
    path=tmp_path/'model.env'
    values={'YHDP_OLLAMA_URL':CFG.url,'YHDP_LLM_MODEL':CFG.generator,'YHDP_EMBED_MODEL':CFG.embedding}
    for key in values:monkeypatch.delenv(key,raising=False)
    path.write_text('\n'.join(k+'='+v for k,v in values.items()))
    assert OllamaConfig.load(path).embedding=='bge-m3'
    assert all(k not in os.environ for k in values)
    monkeypatch.setenv('YHDP_OLLAMA_URL','http://username:password@model.invalid')
    with pytest.raises(RuntimeError):OllamaConfig.load(path)


def test_ollama_implicit_latest_and_changed_model_digest():
    revision = ['v1']
    def wire(request):
        if request.url.path == '/api/tags':
            return httpx.Response(200,json={'models':[
                {'name':CFG.generator,'digest':'generator'},
                {'name':'bge-m3:latest','digest':revision[0]}]})
        return httpx.Response(200,json={'embeddings':[[1.,0.]]})
    gateway = OllamaGateway(CFG,transport=httpx.MockTransport(wire))
    assert gateway.embed(['source']).revision == 'v1'
    revision[0] = 'v2'
    assert gateway.embed(['source']).revision == 'v2'  # no stale digest from the readiness cache
    missing = OllamaGateway(CFG,transport=httpx.MockTransport(lambda request:httpx.Response(200,json={'models':[]})))
    with pytest.raises(GatewayError,match='not_ready'): missing.revisions()


def test_response_from_another_model_is_rejected():
    gateway,_ = model(lambda request,body:httpx.Response(200,json={
        'done':True,'model':'other:latest','message':{'content':'{}'},'embeddings':[[1,0]]}))
    with pytest.raises(GatewayError,match='model_mismatch'): gateway.complete('answer','s',[],'v1')
    with pytest.raises(GatewayError,match='model_mismatch'): gateway.embed(['source'])


def enable(world,gateway):
    for c in world[1]:
        c.app.dependency_overrides[get_gateway]=lambda:gateway
        c.app.state.phase_config=replace(c.app.state.phase_config,provider='ollama')
        c.app.state.worker.cfg=c.app.state.phase_config
        c.app.state.model_gateway=gateway


def index(world,gateway):
    with connect(world[3]) as conn:
        job=embeddings.enqueue(conn,world[1][0].app.state.phase_config,CFG.embedding,settings()['corpus_version'],utcnow())
    def completed():
        with connect(world[3]) as conn:
            state=turns.get(conn,job['id'])
            if state['status'] in ('failed','interrupted'):pytest.fail('index failed: '+str(state['error']))
            return state if state['status']=='completed' else None
    wait(completed,12)
    return job


def test_index_and_hybrid_chat_are_durable_scoped_and_hash_pinned(world):
    from tests.conftest import birth_dose_json
    with connect(world[3]) as conn:reply=birth_dose_json(conn)
    def respond(request,body):
        if request.url.path=='/api/embed':return httpx.Response(200,json={'embeddings':[[1,0,0] for _ in body['input']]})
        return httpx.Response(200,json={'done':True,'message':{'content':reply}})
    gateway,calls=model(respond); enable(world,gateway)
    job=index(world,gateway)
    c=world[1][0]
    assert c.get(f"/v1/chat/turns/{job['id']}").status_code==404
    response=ask(c,key='hybrid')
    assert parse(response)[-1][1]['state']=='answered'
    assert len([x for x in calls if x[0]=='/api/chat'])==1
    assert c.get('/v1/passages/tc-p02').status_code==200
    second=index(world,gateway)
    with connect(world[3]) as conn:
        assert turns.get(conn,second['id'])['result']['embedded']==0
        assert embeddings.ready(conn,CFG.embedding,'test-revision',settings()['corpus_version'])
        conn.execute("update passage set text=text||' updated' where id='tc-p02'")
        assert not embeddings.ready(conn,CFG.embedding,'test-revision',settings()['corpus_version'])
        conn.execute('set role phase_chat')
        # Exercise actual runtime grants, not only the fixture owner's privileges.
        conn.execute("insert into embedding_index(model,revision,corpus_version,dimensions) values ('role-probe','r','v',3)")
        conn.execute("""insert into passage_embedding(passage_id,model,revision,corpus_version,content_hash,embedding)
            values ('tc-p01','role-probe','r','v','hash','[1,0,0]'::vector)""")
        conn.execute("update passage_embedding set content_hash='new-hash' where model='role-probe'")
        assert conn.execute("select content_hash from passage_embedding where model='role-probe'").fetchone()['content_hash']=='new-hash'
        conn.execute("delete from embedding_index where model='role-probe'")
        with pytest.raises(Exception),conn.transaction():conn.execute("update passage set text='forbidden'")
        conn.execute('set role phase_business')
        with pytest.raises(Exception),conn.transaction():conn.execute('select * from passage_embedding')


def test_unknown_provider_call_retains_quarantine_after_redis_recovery(world):
    def respond(request,body):
        if request.url.path=='/api/embed':return httpx.Response(200,json={'embeddings':[[1,0] for _ in body['input']]})
        raise httpx.ReadTimeout('not logged',request=request)
    gateway,calls=model(respond); enable(world,gateway); index(world,gateway)
    response=ask(world[1][0])
    assert parse(response)[-1][1]['turn_status']=='interrupted'
    tid=response.headers['x-turn-id']
    with connect(world[3]) as conn:
        row=conn.execute('select * from ai_model_call where turn_id=%s and ended_at is null',(tid,)).fetchone()
        assert row and row['quarantined'] and row['resource']=='ollama:shared'
    coord=world[1][0].app.state.admission
    coord.r.delete(coord.key('epoch'),coord.key('ready'))
    wait(lambda:coord.ready())
    assert coord.r.hlen(coord.key('slots:ollama:shared'))==1


def test_disabled_provider_serves_history_and_business_without_model(world):
    b,(c,_),fake,_=world
    c.app.state.phase_config=replace(c.app.state.phase_config,provider='disabled')
    assert b.get('/v1/home').status_code==200
    assert c.get('/v1/chat/sessions').status_code==200
    response=ask(c)
    assert response.status_code==503 and response.json()['error']['code']=='ai_disabled'
    assert not fake.calls


def test_tutor_modes_keep_owned_evidence_history_and_default_idempotency(world):
    from tests.conftest import birth_dose_json
    with connect(world[3]) as conn: reply = birth_dose_json(conn)
    world[2].responses = lambda task, messages: reply
    c, other = world[1]
    sid = c.post('/v1/chat/sessions', json={}).json()['id']
    path = f'/v1/chat/sessions/{sid}/messages'
    first = ask(c, key='default-mode', sid=sid)
    assert parse(first)[-1][1]['state'] == 'answered'
    repeat = other.post(path, json={'text':'Vắc xin viêm gan B mũi sơ sinh tiêm khi nào?', 'mode':'auto'},
                        headers={'Idempotency-Key':'default-mode'})
    assert repeat.headers['x-turn-id'] == first.headers['x-turn-id']
    for mode in ('giai_thich','so_sanh','vi_du','tom_tat'):
        response = other.post(path, json={'text':'Làm rõ kiến thức trong nguồn', 'mode':mode},
                              headers={'Idempotency-Key':mode})
        assert parse(response)[-1][1]['mode'] == mode
        assert parse(response)[-1][1]['state'] == 'answered'
    assert c.get(path).json()['items'][-1]['mode'] == 'tom_tat'
    for mode in ('kiem_tra','cham'):
        assert c.post(path, json={'text':'nội dung', 'mode':mode}).status_code == 501


@pytest.mark.parametrize('vectors', [[[0,0]], [[1,float('nan')]], [[True,1]], [], [[1,2],[1]]])
def test_invalid_embedding_vectors_are_not_indexed(vectors):
    gateway,_ = model(lambda request,body:httpx.Response(200,json={'embeddings':vectors})
                      if all(all(not isinstance(v,float) or v == v for v in row) for row in vectors)
                      else httpx.Response(200,content='{"embeddings":[[1,NaN]]}'))
    with pytest.raises(GatewayError): gateway.embed(['one'])
