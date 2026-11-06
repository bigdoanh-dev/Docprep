"""Reproducible illustrative baseline, never a GPU-capacity or clinical-quality benchmark."""
import argparse
import asyncio
import json
import random
import statistics
import time
from pathlib import Path
import httpx


async def run(args):
    tokens = json.loads(Path(args.tokens).read_text(encoding="utf-8"))
    if len(tokens) < args.learners:
        raise SystemExit("Supply one distinct learner token per simulated learner")
    async with httpx.AsyncClient(timeout=30) as verifier:
        checked = await asyncio.gather(*(verifier.get(args.base.rstrip('/')+'/api/v1/me',
            headers={'Authorization':'Bearer '+token}) for token in tokens[:args.learners]))
    if any(response.status_code != 200 for response in checked):
        raise SystemExit('Learner tokens are invalid/expired or the API is unavailable; issue fresh tokens before measuring')
    durations, codes, instances = [], {}, set()
    finish = time.monotonic() + args.seconds
    async def learner(number):
        rng = random.Random(args.seed + number)
        async with httpx.AsyncClient(base_url=args.base.rstrip('/') + '/api/v1',
            headers={"Authorization": "Bearer " + tokens[number]}, timeout=180) as client:
            sid = None
            while time.monotonic() < finish:
                started = time.monotonic()
                try:
                    if rng.random() < args.ai_share:
                        if sid is None:
                            response = await client.post('/chat/sessions', json={})
                            response.raise_for_status()
                            sid = response.json()['id']
                        response = await client.post(f'/chat/sessions/{sid}/messages',
                            json={"text": "Tỷ lệ hiện mắc là gì?"}, headers={"Idempotency-Key": f"load-{args.seed}-{number}-{started}"})
                        kind = "ai"
                        if response.status_code == 200 and 'event: final' not in response.text:
                            raise RuntimeError("missing final")
                    else:
                        path = rng.choice(['/home', '/modules', '/cards/due', '/progress/skills', '/exams'])
                        response = await client.get(path)
                        kind = "business"
                    codes[str(response.status_code)] = codes.get(str(response.status_code), 0) + 1
                    instances.add(response.headers.get('X-Service-Instance', 'unknown'))
                    durations.append((kind, time.monotonic() - started))
                except Exception:
                    codes['transport_error'] = codes.get('transport_error', 0) + 1
                await asyncio.sleep(rng.uniform(args.think_min, args.think_max))
    await asyncio.gather(*(learner(i) for i in range(args.learners)))
    def percentiles(values):
        values = sorted(values)
        return {"n": len(values), "p50_s": statistics.median(values) if values else None,
                "p95_s": values[min(len(values)-1, int(len(values)*.95))] if values else None}
    report = {"scope": "illustrative local baseline; no approved SLO or real-model capacity claim",
              "config": {k: v for k, v in vars(args).items() if k not in ('tokens',)}, "status_codes": codes,
              "instances": sorted(instances), "business": percentiles([d for k,d in durations if k=='business']),
              "ai": percentiles([d for k,d in durations if k=='ai'])}
    report['valid_authentication'] = not (codes.get('401') or codes.get('403'))
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report['valid_authentication']:
        raise SystemExit('Authentication expired during measurement; this report is not a valid learner baseline')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', default='http://127.0.0.1:18880')
    parser.add_argument('--tokens', required=True, help='ignored JSON file with distinct bearer tokens; never print or commit')
    parser.add_argument('--learners', type=int, choices=(30,40,50), required=True)
    parser.add_argument('--seconds', type=int, default=60)
    parser.add_argument('--ai-share', type=float, default=.1, help='illustrative workload, not Lead-approved')
    parser.add_argument('--think-min', type=float, default=1)
    parser.add_argument('--think-max', type=float, default=3)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--output', required=True)
    options = parser.parse_args()
    if not 0 <= options.ai_share <= 1 or options.seconds <= 0 or options.think_min < 0 or options.think_max < options.think_min:
        parser.error('Invalid workload parameters')
    asyncio.run(run(options))
