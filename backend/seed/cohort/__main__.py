"""python -m seed.cohort: generate the sample cohort in the database DATABASE_URL names."""
import argparse
import json
import sys
from datetime import datetime, time, timezone


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m seed.cohort",
                                     description="A sample question bank and synthetic learners; dev and test only.")
    parser.add_argument("--learners", type=int, default=300)
    parser.add_argument("--weeks", type=int, default=12)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--end", help="last day of the cohort's history, YYYY-MM-DD; default: now")
    args = parser.parse_args(argv)

    from app.config import require_dev_env
    from app.db import connect
    from seed import cohort

    end = None
    if args.end:
        end = datetime.combine(datetime.strptime(args.end, "%Y-%m-%d").date(), time(12), tzinfo=timezone.utc)
    try:
        require_dev_env("seed.cohort")
        with connect() as conn:
            result = cohort.run(conn, args.learners, args.weeks, args.seed, end)
    except (RuntimeError, ValueError) as e:
        sys.exit(str(e))
    # A Windows console is often not UTF-8, and the summary holds Vietnamese names.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
