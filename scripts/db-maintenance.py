"""Binary-safe local pg_dump/restore through Docker; never restores over a used database."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PREFIX = ["docker", "compose", "exec", "-T", "db"]


def command(*args, **kwargs):
    return subprocess.run(PREFIX + list(args), cwd=ROOT, check=True, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    backup = sub.add_parser("backup")
    backup.add_argument("--output", type=Path)
    restore = sub.add_parser("restore")
    restore.add_argument("archive", type=Path)
    restore.add_argument("--database", help="new database only; must start with alphav1_restore_")
    args = parser.parse_args()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    if args.action == "backup":
        dest = (args.output or ROOT / "backups" / f"alpha_{stamp}.dump").resolve()
        dest.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive creation: an existing archive is never overwritten.
        with dest.open("xb") as output:
            command("pg_dump", "-U", "alpha", "-d", "alphav1", "-Fc", stdout=output)
        print(f"Backup: {dest} ({dest.stat().st_size} bytes)")
    else:
        archive = args.archive.resolve(strict=True)
        database = args.database or f"alphav1_restore_{stamp}"
        if not re.fullmatch(r"alphav1_restore_[a-z0-9_]{1,40}", database):
            parser.error("Restore target must be a new alphav1_restore_* database")
        # createdb fails if the target exists; no DROP, --clean, or overwrite path is offered.
        command("createdb", "-U", "alpha", database)
        with archive.open("rb") as source:
            command("pg_restore", "-U", "alpha", "-d", database, "--exit-on-error", "--single-transaction", stdin=source)
        command("psql", "-U", "alpha", "-d", database, "-v", "ON_ERROR_STOP=1", "-c",
                "select version_num from alembic_version; "
                "select 'learner' as entity,count(*) from learner union all "
                "select 'responses',count(*) from item_response union all "
                "select 'attempts',count(*) from exam_attempt union all "
                "select 'messages',count(*) from chat_message;")
        print(f"Restore verified in separate database: {database}")


if __name__ == "__main__":
    main()
