"""Local deployment acceptance: real proxy/replicas, Redis restart, failover, backup restore.

Only operates on the explicitly named docprep-phase1 Compose project. No external model calls.
"""
import concurrent.futures
import json
from pathlib import Path
import subprocess
import time
import uuid
import httpx

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ['docker','compose','--env-file','.env.phase1','-f','deploy/compose.phase1.yml']


def command(*args, stdin=None):
    result = subprocess.run(COMPOSE + list(args), input=stdin, cwd=ROOT, text=True, encoding='utf-8', capture_output=True)
    if result.returncode:
        # Never dump environment-containing command output in a public report.
        raise RuntimeError('Phase 1 operation failed: ' + ' '.join(args[:3]))
    return result.stdout.strip()


def sql(query, database='phase1'):
    return command('exec','-T','db','psql','-U','phase_owner','-d',database,'-At',stdin=query)


def wait_ready(client):
    end = time.monotonic()+45
    while time.monotonic() < end:
        try:
            path = '/api/v1/chat/turns/active' if 'authorization' in client.headers else '/api/health'
            if client.get(path).status_code == 200: return
        except httpx.HTTPError: pass
        time.sleep(.5)
    raise AssertionError('Proxy did not recover')


def fingerprints(database):
    # Identifiers originate solely in the catalog; quote_ident is applied by PostgreSQL.
    tables = sql("select tablename from pg_tables where schemaname='public' order by tablename",database).splitlines()
    statements = []
    for table in tables:
        name = '"' + table.replace('"','""') + '"'
        literal = "'" + table.replace("'", "''") + "'"
        statements.append(f"select json_build_object('table',{literal},'digest',count(*)::text || ':' || md5(coalesce(string_agg(v,',' order by v),'')))::text from (select to_jsonb(t)::text v from {name} t) x")
    rows = [json.loads(line) for line in sql(' union all '.join(statements),database).splitlines()]
    return {row['table']: row['digest'] for row in rows}


def main():
    report = {}
    with httpx.Client(base_url='http://127.0.0.1:18880', timeout=180) as client:
        wait_ready(client)
        for path in ['/api/v1/missing','/v1/missing','/api/v1','/v1','/api','/api/missing']:
            r=client.get(path); assert r.status_code==404 and r.headers['content-type'].startswith('application/json')
        for path in ['/metrics','/api/metrics','/readyz','/api/readyz']:
            assert client.get(path).status_code==404
        report['routing_and_private_endpoints']='pass'
        code=command('run','--rm','--no-deps','seed','python','-m','seed.browser')
        token=client.post('/api/v1/auth/activate',json={'code':code}).json()['access_token']
        client.headers['Authorization']='Bearer '+token
        consent=client.get('/api/v1/consent/current').json()
        assert client.post('/api/v1/consent',json={'version':consent['version'],'service':True,'research':False}).is_success
        questions=[('Tỷ lệ hiện mắc là gì?','answered'),('Tỷ lệ mắc là gì?','needs_clarification'),
                   ('Con tôi sốt cao nên uống thuốc gì?','declined'),('Vật lý lượng tử là gì?','insufficient_evidence')]
        for text,expected in questions:
            sid=client.post('/api/v1/chat/sessions',json={}).json()['id']
            key=uuid.uuid4().hex
            path=f'/api/v1/chat/sessions/{sid}/messages'
            response=client.post(path,json={'text':text},headers={'Idempotency-Key':key})
            assert response.status_code==200, response.status_code
            pairs=[]; event=''
            for line in response.text.splitlines():
                if line.startswith('event:'): event=line[6:].strip()
                if line.startswith('data:'): pairs.append((event,json.loads(line[5:])))
            assert pairs[-1][0]=='final' and pairs[-1][1]['state']==expected, pairs[-1]
            answer=next(data for name,data in pairs if name=='answer')
            if expected=='answered':
                assert answer['citations']
                assert client.get('/api/v1/passages/'+answer['citations'][0]['passage_id']).is_success
            tid=response.headers['x-turn-id']
            assert client.post(path,json={'text':text},headers={'Idempotency-Key':key}).headers['x-turn-id']==tid
        report['four_ai_states_citations_idempotency']='pass'
        def probe(_):
            with httpx.Client(base_url=client.base_url,headers=client.headers,timeout=30) as other:
                return other.get('/api/v1/me').headers.get('x-service-instance')
        with concurrent.futures.ThreadPoolExecutor(8) as pool:
            instances=set(pool.map(probe,range(24)))
        assert len(instances)==2, instances
        report['business_instances']=sorted(instances)
        command('restart','redis')
        time.sleep(6)
        wait_ready(client)
        # After Redis loses all state, completed results remain readable and events recover from snapshots.
        assert client.get(f'/api/v1/chat/turns/{tid}').json()['turn_status']=='completed'
        assert 'event: final' in client.get(f'/api/v1/chat/turns/{tid}/events').text
        report['redis_restart']='pass'
        command('kill','-s','SIGKILL','chat-1')
        try:
            # One complete health interval plus timeout and scheduling margin.
            # POST is never replayed by the proxy; only send after it withdrew the dead upstream.
            time.sleep(8)
            wait_ready(client)
            assert client.get('/api/health').is_success
            session=client.post('/api/v1/chat/sessions',json={})
            assert session.status_code == 200, f'Failover session HTTP {session.status_code}'
            sid=session.json()['id']
            result=client.post(f'/api/v1/chat/sessions/{sid}/messages',json={'text':'Tỷ lệ hiện mắc là gì?'})
            assert result.is_success and '"state":"answered"' in result.text
        finally:
            command('up','-d','--no-deps','chat-1')
        report['chat_replica_failover']='pass'
    # Stop new claims, then compare an immutable snapshot with its separate restored database.
    for service in ['chat-1','chat-2']:
        command('exec','-T',service,'python','-m','app.phase_cli','drain')
    restore='phase1_restore_'+uuid.uuid4().hex[:12]
    dump='/backups/acceptance-'+uuid.uuid4().hex+'.dump'
    try:
        deadline=time.monotonic()+30
        while sql("select count(*) from ai_turn where status in ('queued','running')")!='0':
            if time.monotonic()>deadline: raise AssertionError('Outstanding turns before backup')
            time.sleep(.2)
        original=fingerprints('phase1')
        command('exec','-T','db','pg_dump','-U','phase_owner','-d','phase1','-Fc','--no-owner','-f',dump)
        command('exec','-T','db','createdb','-U','phase_owner',restore)
        command('exec','-T','db','pg_restore','-U','phase_owner','-d',restore,'--no-owner','--exit-on-error',dump)
        recovered=fingerprints(restore)
        assert original==recovered
        report['backup_restore']={'tables_matched':len(original),'restore_database':restore,'dump':dump}
        command('up','-d','--no-deps','--force-recreate','--wait','db')
        assert fingerprints('phase1')==original
        report['postgres_volume_recreate']={'tables_matched':len(original)}
    finally:
        command('up','-d','--no-deps','--force-recreate','chat-1','chat-2')
    ROOT.joinpath('.local/phase1-deployment.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__': main()
