"""Backup content DB/assets; restore only to a newly named DB and volume, never overwrite live data."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import subprocess
import tarfile
import re
import hashlib

ROOT=Path(__file__).resolve().parents[1]
COMPOSE=['docker','compose','--env-file','.env.content','-f','deploy/compose.content.yml']


def run(args):
    r=subprocess.run(args,cwd=ROOT,capture_output=True,text=True,encoding='utf-8')
    if r.returncode:raise RuntimeError('Content backup/restore operation failed: '+' '.join(args[:3]))
    return r.stdout.strip()


def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['backup','restore']);p.add_argument('directory',nargs='?');args=p.parse_args()
    stamp=datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
    if args.action=='backup':
        target=ROOT/'backups'/'content'/stamp;target.mkdir(parents=True,exist_ok=False)
        run(COMPOSE+['exec','-T','content-db','pg_dump','-U','content_owner','-d','content_workspace','-Fc','--no-owner','-f','/tmp/content.dump'])
        run(COMPOSE+['cp','content-db:/tmp/content.dump',str(target/'content.dump')])
        # Stream binary data directly: Docker cp cannot read a container's tmpfs reliably.
        with (target/'assets.tar.gz').open('wb') as archive:
            result=subprocess.run(COMPOSE+['exec','-T','content-api','tar','-C','/content-assets','-czf','-','.'],cwd=ROOT,stdout=archive,stderr=subprocess.PIPE)
        if result.returncode:raise RuntimeError('Asset backup failed')
        hashes={name:hashlib.sha256((target/name).read_bytes()).hexdigest() for name in ('content.dump','assets.tar.gz')}
        (target/'manifest.json').write_text(json.dumps({'schema':'content.backup.v1','created_at':stamp,'sha256':hashes}),encoding='utf-8')
        print(target)
    else:
        if not args.directory:p.error('Provide a backup directory')
        source=Path(args.directory).resolve()
        if not (source/'content.dump').is_file():raise ValueError('Missing content.dump')
        manifest=json.loads((source/'manifest.json').read_text(encoding='utf-8'))
        if manifest.get('schema')!='content.backup.v1':raise ValueError('Unsupported backup manifest')
        for name in ('content.dump','assets.tar.gz'):
            if hashlib.sha256((source/name).read_bytes()).hexdigest()!=manifest.get('sha256',{}).get(name):
                raise ValueError('Backup checksum mismatch: '+name)
        with tarfile.open(source/'assets.tar.gz') as archive:
            for member in archive.getmembers():
                if member.name not in ('.','./') and not (member.isfile() and re.fullmatch(r'(?:\./)?[a-f0-9]{64}',member.name)):
                    raise ValueError('Unsafe asset archive entry')
        database='content_restore_'+stamp;volume='docprep_content_restore_assets_'+stamp
        run(COMPOSE+['exec','-T','content-db','createdb','-U','content_owner',database])
        run(COMPOSE+['cp',str(source/'content.dump'),'content-db:/tmp/content-restore.dump'])
        run(COMPOSE+['exec','-T','content-db','pg_restore','-U','content_owner','-d',database,'--no-owner','--exit-on-error','/tmp/content-restore.dump'])
        run(['docker','volume','create',volume])
        run(['docker','run','--rm','--user','0','-v',volume+':/restore','--mount',f'type=bind,source={source},target=/backup,readonly',
             'docprep-content-backend:local','python','-c',"import tarfile,os,pathlib; tarfile.open('/backup/assets.tar.gz').extractall('/restore',filter='data'); os.chown('/restore',10001,10001); [(os.chown(str(p),10001,10001),os.chmod(str(p),0o644)) for p in pathlib.Path('/restore').iterdir()]"])
        print(json.dumps({'database':database,'asset_volume':volume,'live_data_changed':False}))


if __name__=='__main__':main()
