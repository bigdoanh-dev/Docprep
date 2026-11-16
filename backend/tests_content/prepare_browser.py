"""Explicitly reset ONLY content_workspace_test for the real browser/API QA flow."""
import json
import os
from pathlib import Path
from urllib.parse import urlsplit
from app.content import auth, db, importer


def main():
    url=os.environ['CONTENT_TEST_DATABASE_URL']
    if (os.environ.get('APP_ENV')!='test' or os.environ.get('CONTENT_QA_RESET')!='1'
            or urlsplit(url).path!='/content_workspace_test'):
        raise RuntimeError('Explicit test environment and CONTENT_QA_RESET=1 are required')
    mapping=json.loads(Path(os.environ['CONTENT_TEST_MAPPING']).read_text(encoding='utf-8'))
    if mapping.get('version')!='AUTOMATED-QA-ONLY':
        raise ValueError('Only the synthetic AUTOMATED-QA-ONLY mapping fixture is allowed')
    password=os.environ['CONTENT_E2E_PASSWORD']
    if len(password)<12:raise ValueError('Provide a separate QA password with at least 12 characters')
    os.environ['CONTENT_DATABASE_URL']=url
    with db.connect() as conn:
        conn.execute('drop schema if exists public cascade; create schema public')
    db.migrate()
    with db.connect() as conn:
        uid=auth.create_user(conn,'reviewer.e2e',password,'Automated QA',['editor','reviewer','publisher'])
        package=importer.Package(os.environ['CONTENT_TEST_SOURCE'])
        try:
            result=importer.apply(conn,package,{'id':uid,'roles':['editor','reviewer','publisher']},mapping,'qd2760')
        finally:package.close()
    print(json.dumps({'database':'content_workspace_test','chunks':result['added_chunks'],'clinical_approval':False}))


if __name__=='__main__':main()
