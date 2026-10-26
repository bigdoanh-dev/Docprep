"""Developer commands: python -m app.cli <command>."""
import argparse
import sys

import yaml

from app.main import create_app
from app.openapi import OPENAPI_PATH, build_openapi, dump_openapi


def export_openapi(check: bool) -> int:
    spec = build_openapi(create_app("mock"))
    if not check:
        OPENAPI_PATH.write_text(dump_openapi(spec), encoding="utf-8", newline="\n")
        print(f"wrote {OPENAPI_PATH}")
        return 0
    current = yaml.safe_load(OPENAPI_PATH.read_text(encoding="utf-8")) if OPENAPI_PATH.exists() else None
    if current != spec:
        print(f"{OPENAPI_PATH.name} is out of date. Run: python -m app.cli export-openapi", file=sys.stderr)
        return 1
    return 0


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export-openapi", help="write openapi.yaml from the code")
    export.add_argument("--check", action="store_true", help="write nothing; fail when the file is out of date")
    commands.add_parser("migrate", help="build or upgrade the database schema; safe to repeat")
    commands.add_parser("load-blueprint",
                        help="load the exam blueprint, the competency tree and the học phần; every environment")
    staff = commands.add_parser(
        "create-staff", help="create a reviewer, admin or ministry viewer; the password comes from "
                             "STAFF_PASSWORD or is asked for")
    staff.add_argument("--email", required=True)
    staff.add_argument("--name", required=True)
    staff.add_argument("--role", required=True, choices=("reviewer", "admin", "ministry_viewer"))
    commands.add_parser("seed", help="load the blueprint, the demo content and a dev learner; dev and test only")
    alpha = commands.add_parser("seed-alpha", help="repeatable local learner, staff and sample dashboard setup")
    alpha.add_argument("--no-cohort", action="store_true", help="skip the sample dashboard history")
    commands.add_parser("reset-dev", help="empty every table, then seed; dev and test only")
    args = parser.parse_args(argv)
    if args.command == "export-openapi":
        code = export_openapi(args.check)
        if code:
            sys.exit(code)
    elif args.command == "migrate":
        from app.db import migrate
        migrate()
        print("database schema is up to date")
    elif args.command == "load-blueprint":
        from app.db import connect
        from seed import run_blueprint

        with connect() as conn:
            run_blueprint(conn)
        print("blueprint loaded")
    elif args.command == "create-staff":
        import getpass
        import os

        from app.db import connect
        from app.services.auth import create_staff

        password = os.environ.get("STAFF_PASSWORD")
        if not password:
            password = getpass.getpass("Password: ")
            if getpass.getpass("Again: ") != password:
                sys.exit("the two passwords differ")
        try:
            with connect() as conn:
                staff_id = create_staff(conn, args.email, password, args.name, args.role)
        except ValueError as e:
            sys.exit(str(e))
        print(f"created staff account {staff_id} ({args.role})")
    elif args.command == "seed-alpha":
        import json
        from app.db import connect
        from seed.alpha import run
        with connect() as conn:
            summary = run(conn, with_cohort=not args.no_cohort)
        print(json.dumps(summary, ensure_ascii=True, default=str))
    elif args.command in ("seed", "reset-dev"):
        from app.config import require_dev_env
        from app.db import connect, truncate_all
        from seed import run_seed

        try:
            require_dev_env(args.command)
        except RuntimeError as e:
            sys.exit(str(e))
        with connect() as conn:
            if args.command == "reset-dev":
                truncate_all(conn)
            run_seed(conn)
        print("seeded")


if __name__ == "__main__":
    main()
