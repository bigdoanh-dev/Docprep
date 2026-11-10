"""Issue a fresh activation code or password account for browser runs, in dev/test only."""
import argparse
import json
from uuid import uuid4

from app.auth.secrets import hash_code
from app.config import require_dev_env
from app.db import connect


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--password-account", action="store_true")
    args = parser.parse_args()
    require_dev_env("browser test fixture")
    if args.password_account:
        from app.services.auth import create_password_learner
        from app.auth.secrets import new_token
        username, password = "e2e." + uuid4().hex[:20], new_token("test")
        with connect() as conn:
            learner_id = create_password_learner(conn, username, password, "Browser test")
            conn.execute("update learner set is_synthetic=true where id=%s", (learner_id,))
        # Explicit test-only fixture; caller keeps these credentials in memory, never in test logs.
        print(json.dumps({"username": username, "password": password}))
        return
    code = f"ALPHA-E2E-{uuid4().hex[:16].upper()}"
    with connect() as conn:
        conn.execute("insert into activation_code(code_hash, audience) values (%s, 'student')", (hash_code(code),))
    print(code)


if __name__ == "__main__":
    main()
