"""Verify HTTPS + authenticated SSE using an isolated local Caddy CA, not verify=False."""
import json
from pathlib import Path
import ssl
import subprocess
import time
import uuid
import httpx
from verify_phase1_support import compose


def main():
    override=['-f','deploy/compose.tls-local.yml']
    compose(override+['up','-d','--no-deps','caddy'])
    try:
        ca=Path('.local/phase1-local-ca.crt')
        deadline=time.monotonic()+45
        while True:
            result=subprocess.run(['docker','cp','docprep-phase1-caddy-1:/data/caddy/pki/authorities/local/root.crt',str(ca)],capture_output=True)
            if result.returncode==0: break
            if time.monotonic()>deadline: raise AssertionError('Local CA did not initialise')
            time.sleep(.5)
        context=ssl.create_default_context(cafile=str(ca))
        with httpx.Client(base_url='https://localhost:18443', verify=context, timeout=45) as client:
            for _ in range(60):
                try:
                    if client.get('/api/health').is_success: break
                except httpx.HTTPError: pass
                time.sleep(.5)
            code=compose(['run','--rm','--no-deps','seed','python','-m','seed.browser'])
            pair=client.post('/api/v1/auth/activate',json={'code':code}).json()
            client.headers['Authorization']='Bearer '+pair['access_token']
            text=client.get('/api/v1/consent/current').json()
            assert client.post('/api/v1/consent',json={'version':text['version'],'service':True,'research':False}).is_success
            sid=client.post('/api/v1/chat/sessions',json={}).json()['id']
            events=[]
            with client.stream('POST',f'/api/v1/chat/sessions/{sid}/messages',json={'text':'Tỷ lệ hiện mắc là gì?'},headers={'Idempotency-Key':uuid.uuid4().hex}) as response:
                assert response.status_code==200 and response.headers['content-type'].startswith('text/event-stream')
                for line in response.iter_lines():
                    if line.startswith('event:'): events.append(line[6:].strip())
            assert events[-1]=='final' and 'answer' in events and 'step' in events
        report={'https_verified_with_local_ca':True,'sse_events':events,'scope':'localhost only; no public DNS/ACME deployment claim'}
        Path('.local/phase1-tls.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps(report))
    finally:
        compose(['up','-d','--no-deps','caddy'])


if __name__=='__main__': main()
