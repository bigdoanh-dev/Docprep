"""Explicit Phase 1 migration, contract and operations commands. No app/gateway startup."""
import argparse
import json
import os
from pathlib import Path
import signal
import time
from uuid import UUID
import yaml
from app.db import connect, migrate
from app.config import ROOT_DIR
from app.openapi import dump_openapi


def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("migrate")
    contract = commands.add_parser("export-openapi")
    contract.add_argument("--check", action="store_true")
    release = commands.add_parser("release-model-call")
    release.add_argument("call_id", type=UUID)
    release.add_argument("--confirm-stopped", action="store_true", required=True)
    commands.add_parser("drain")
    load = commands.add_parser("seed-load")
    load.add_argument("--learners", type=int, choices=(30,40,50), default=50)
    load.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.command == "migrate":
        migrate()
        grants = Path(__file__).resolve().parents[1] / "phase-grants.sql"
        if not grants.exists():
            grants = ROOT_DIR / "deploy" / "grants.sql"
        with connect() as conn:
            conn.execute(grants.read_text(encoding="utf-8"))
        print("phase1 migration and grants complete")
    elif args.command == "export-openapi":
        from app.phase_routes import combined_openapi
        target = ROOT_DIR / "openapi.yaml"
        spec = combined_openapi()
        if args.check:
            if yaml.safe_load(target.read_text(encoding="utf-8")) != spec:
                raise SystemExit("Phase 1 OpenAPI drift")
        else:
            target.write_text(dump_openapi(spec), encoding="utf-8", newline="\n")
    elif args.command == "seed-load":
        from app.config import require_dev_env, settings
        from app.repo.learners import create
        from app.repo.consent import give
        from app.services.auth import issue_tokens
        from datetime import datetime, timezone
        import uuid
        require_dev_env("seed-load")
        tokens = []
        with connect() as conn:
            now, batch = datetime.now(timezone.utc), uuid.uuid4().hex[:8]
            for n in range(args.learners):
                lid = create(conn, f"HV-LOAD-{batch}-{n}", None, "student", "2027-03-15", .9, "Load test synthetic")
                conn.execute("update learner set is_synthetic=true where id=%s", (lid,))
                give(conn, lid, "service", settings()["consent"]["version"], now)
                tokens.append(issue_tokens(conn, "learner", lid, now).access_token)
        Path(args.output).write_text(json.dumps(tokens), encoding="utf-8")
        print(f"Created {args.learners} synthetic load learners; tokens written to private output file")
    elif args.command == "release-model-call":
        with connect() as conn:
            row = conn.execute("update ai_model_call set ended_at=now(),quarantined=false where id=%s and ended_at is null returning id",
                               (args.call_id,)).fetchone()
        print("released" if row else "already ended or not found")
    elif args.command == "drain":
        if not hasattr(signal, "SIGUSR1"):
            raise SystemExit("Run drain inside the Linux service container")
        os.kill(1, signal.SIGUSR1)
        print("drain requested; check /readyz internally before replacement")


if __name__ == "__main__":
    main()
