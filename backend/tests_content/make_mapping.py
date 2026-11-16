"""Synthetic browser fixture only; the ordinal mapping has NO clinical meaning."""
import json
import zipfile
from pathlib import Path
import yaml


def main():
    root=Path(__file__).resolve().parents[2]/'.local'/'content'
    reference=json.loads((root/'mapping.reference.json').read_text(encoding='utf-8'))
    with zipfile.ZipFile(root/'input'/'data.zip') as package:
        taxonomy=yaml.safe_load(package.read('data/blueprint/qd51.yaml'))
    domains=[d['id'] for group in taxonomy['mien'] for d in group['sub']]
    targets=reference['runtime_domain_reference']
    if len(domains)!=len(targets):raise ValueError('Fixture assumptions changed; inspect the two taxonomies')
    mapping={'version':'AUTOMATED-QA-ONLY','approved':True,
        'notice':'Synthetic test mapping; never a clinical mapping or approval.',
        'issues':reference['issues'],'domains':dict(zip(domains,[d['id'] for d in targets]))}
    (root/'mapping.test.json').write_text(json.dumps(mapping,ensure_ascii=False),encoding='utf-8')
    print('Wrote .local/content/mapping.test.json for the disposable test DB only; NOT a clinical mapping.')


if __name__=='__main__':main()
