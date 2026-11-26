"""Operator tools; passwords come from prompts/environment, never command arguments."""
import argparse
import getpass
import json
import os
from pathlib import Path
from . import auth, db, importer, publication


def main():
    parser=argparse.ArgumentParser()
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('migrate')
    for name in ('create-user','reset-password'):
        p=sub.add_parser(name);p.add_argument('--username',required=True)
        if name=='create-user':p.add_argument('--name',required=True);p.add_argument('--roles',nargs='+',required=True)
    for name in ('preview','import'):
        p=sub.add_parser(name);p.add_argument('package');p.add_argument('--document');p.add_argument('--mapping')
    p=sub.add_parser('taxonomy');p.add_argument('--mapping',required=True)
    p=sub.add_parser('accept-baseline');p.add_argument('package');p.add_argument('--reason',required=True);p.add_argument('--apply',action='store_true')
    p=sub.add_parser('export');p.add_argument('--version',required=True);p.add_argument('--chunks',nargs='+',required=True);p.add_argument('--output',required=True)
    p=sub.add_parser('publish');p.add_argument('package');p.add_argument('--verify-only',action='store_true')
    for name in ('activate','revoke'):
        p=sub.add_parser(name);p.add_argument('--version',required=True);p.add_argument('--reason',required=True);p.add_argument('--channel',default='local')
    p=sub.add_parser('mapping-template');p.add_argument('--output',required=True)
    p=sub.add_parser('export-openapi');p.add_argument('--output',required=True)
    p=sub.add_parser('rechunk',help='Build review candidates from original DOCX files')
    p.add_argument('package', help='data.zip providing data/sources.yaml')
    p.add_argument('--sources',required=True,help='Folder with <doc_id>.docx')
    p.add_argument('--output',required=True,help='New directory for review artifacts')
    p.add_argument('--document',action='append',help='Source ID. Repeat to choose several')
    p.add_argument('--tesseract')
    p.add_argument('--ocr-languages',default='vie+eng')
    p.add_argument('--ocr-workers',type=int,default=4)
    p.add_argument('--tessdata',help='Folder with vie/eng .traineddata (Tesseract --tessdata-dir)')
    p.add_argument('--ocr-cache',help='Folder reusing Tesseract TSV per page image (keyed by image hash)')
    p.add_argument('--apply',action='store_true',help='Create pending revisions in the content DB')
    args=parser.parse_args()
    if args.command=='rechunk':
        from app.content_tools.rechunk import build, registry, write_json
        sources=registry(Path(args.package))
        ids=list(dict.fromkeys(args.document or sources))
        if unknown := set(ids) - sources.keys():
            parser.error(f'Unknown source IDs: {", ".join(sorted(unknown))}')
        files=[(sources[doc],Path(args.sources)/f'{doc}.docx') for doc in ids]
        for source,path in files:
            if not path.is_file() or not path.stat().st_size:
                parser.error(f'Missing original: {path}')
            if source.format=='scan' and not args.tesseract:
                parser.error(f'{source.doc_id} requires --tesseract')
        output=Path(args.output)
        output.mkdir(parents=True,exist_ok=False)
        prepared=[]
        for source,path in files:
            folder=output/source.doc_id
            report,rows=build(source,path,folder,tesseract=args.tesseract,
                              ocr_languages=args.ocr_languages,workers=args.ocr_workers,
                              ocr_cache=args.ocr_cache,tessdata=args.tessdata)
            prepared.append((source,path,folder,report,rows))
        result={'documents':[p[3] for p in prepared]}
        if args.apply:
            import zipfile
            import yaml
            from .rechunk_import import apply
            with zipfile.ZipFile(args.package) as source_zip:
                info=source_zip.getinfo('data/blueprint/qd51.yaml')
                if info.file_size>1024**2:
                    parser.error('Source taxonomy is too large')
                taxonomy=yaml.safe_load(source_zip.read(info))
            with db.connect() as conn:
                db.check_ready(conn)
                username=os.environ.get('CONTENT_USERNAME') or input('Content username: ')
                password=os.environ.get('CONTENT_PASSWORD') or getpass.getpass('Content password: ')
                user=auth.password_user(conn,username,password)
                user['roles']=auth.roles(conn,user['id'])
                result['revisions']=apply(conn,user,prepared,taxonomy)
        write_json(output/'report.json',result)
        print(json.dumps({'output':str(output),'documents':ids,'chunks':sum(len(p[4]) for p in prepared),
                          'revisions':result.get('revisions',[])},ensure_ascii=False))
        return
    if args.command=='migrate':db.migrate();print('Content schema ready');return
    if args.command=='export-openapi':
        import yaml
        from app.main_content import create_app
        Path(args.output).write_text(yaml.safe_dump(create_app().openapi(),allow_unicode=True,sort_keys=False),encoding='utf-8');return
    if args.command=='preview':
        package=importer.Package(args.package)
        try:print(json.dumps(package.report(),ensure_ascii=False))
        finally:package.close()
        return
    if args.command in ('publish','activate','revoke','mapping-template'):
        publication.dev_only()
        with publication.runtime_connect() as conn:
            actor=conn.execute('select current_user as actor').fetchone()['actor']
            if actor!='phase_publisher':raise RuntimeError('Use the restricted phase_publisher DB role')
            if args.command=='publish':
                package=publication.load_package(args.package)
                # verify-only rolls back all validation writes, including candidate projection.
                result=publication.publish(conn,package,actor)
                if args.verify_only:conn.rollback();result['verified_only']=True
            elif args.command=='mapping-template':
                issues={str(r['id']):{'runtime_issue_id':r['id'],'competency_code':r['code'],'name':r['name']} for r in
                    conn.execute('select i.id,i.name,n.code from core_issue i join competency_node n on n.core_issue_id=i.id')}
                domains=[dict(r) for r in conn.execute('select id,name from exam_competency_component order by id')]
                Path(args.output).write_text(json.dumps({'version':'FILL_AFTER_REVIEW','approved':False,'issues':issues,
                    'domains':{},'runtime_domain_reference':domains},ensure_ascii=False,indent=2),encoding='utf-8')
                result={'output':args.output,'notice':'Map source domain codes explicitly and obtain review; template is not approved.'}
            else:result=publication.activate(conn,args.version,actor,args.reason,args.channel,args.command=='revoke')
        print(json.dumps(result,ensure_ascii=False));return
    with db.connect() as conn:
        if args.command in ('create-user','reset-password'):
            if conn.execute('select current_user actor').fetchone()['actor']!='content_owner':
                raise RuntimeError('Account provisioning requires the content_owner operator connection')
            password=os.environ.get('CONTENT_PASSWORD') or getpass.getpass('Password (12–1024 characters): ')
            if not os.environ.get('CONTENT_PASSWORD') and password!=getpass.getpass('Confirm password: '):raise ValueError('Passwords differ')
            if args.command=='create-user':
                uid=auth.create_user(conn,args.username,password,args.name,args.roles)
            else:
                if not 12<=len(password)<=1024:raise ValueError('Invalid password length')
                row=conn.execute('select id from content_user where username=%s for update',(args.username,)).fetchone()
                if not row:raise ValueError('Unknown content account')
                uid=row['id'];conn.execute('update content_user set password_hash=%s where id=%s',(auth.hash_password(password),uid))
                conn.execute('update content_token set revoked=true where user_id=%s',(uid,));auth.audit(conn,uid,'password_reset',uid)
            print(json.dumps({'user_id':str(uid)}));return
        username=os.environ.get('CONTENT_USERNAME') or input('Content username: ')
        password=os.environ.get('CONTENT_PASSWORD') or getpass.getpass('Content password: ')
        user=auth.password_user(conn,username,password);user['roles']=auth.roles(conn,user['id'])
        if args.command=='import':
            package=importer.Package(args.package)
            try:result=importer.apply(conn,package,user,json.loads(Path(args.mapping).read_text(encoding='utf-8')) if args.mapping else None,args.document)
            finally:package.close()
        elif args.command=='accept-baseline':
            from . import baseline
            package=importer.Package(args.package)
            try:result=baseline.accept(conn,package,user,args.reason,args.apply)
            finally:package.close()
        elif args.command=='taxonomy':
            auth.require(user,'reviewer')
            previous=conn.execute('select payload from taxonomy_snapshot limit 1').fetchone()
            if not previous:raise ValueError('Import source taxonomy first')
            version=importer.add_taxonomy(conn,previous['payload'],json.loads(Path(args.mapping).read_text(encoding='utf-8')),user)
            auth.audit(conn,user['id'],'mapping_snapshot',version);result={'taxonomy_version':version}
        else:
            result=publication.export_release(conn,user,args.version,args.chunks)
            Path(args.output).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
            result={'output':args.output,'manifest_sha256':result['manifest_sha256'],'trust':'local_dev'}
        print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
