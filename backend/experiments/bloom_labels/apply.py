"""Writes the agreed machine labels (labels.jsonl) into question_bloom_label (source 'machine') of the
database in DATABASE_URL, which needs the owner role. Approved questions are immutable, so
question.bloom_level_6 is left for reviewed labels; the chat reads that first, then this table."""
import json
import sys
from pathlib import Path

from app.db import connect

HERE = Path(__file__).resolve().parent


def main() -> int:
    rows = [json.loads(l) for l in (HERE / "labels.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    with connect() as conn:
        n = 0
        for r in rows:
            if r["agreed"]:
                n += conn.execute("""insert into question_bloom_label (question_id, question_version, level)
                                     values (%s, %s, %s) on conflict (question_id, question_version)
                                     do update set level = excluded.level where question_bloom_label.source = 'machine'""",
                                  (r["id"], r["version"], r["agreed"])).rowcount
    print(f"{n} questions labelled", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
