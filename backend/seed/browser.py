"""Issue one fresh activation code for a repeatable browser run, in dev/test only."""
from uuid import uuid4

from app.auth.secrets import hash_code
from app.config import require_dev_env
from app.db import connect


def main():
    require_dev_env("browser test fixture")
    code = f"ALPHA-E2E-{uuid4().hex[:16].upper()}"
    with connect() as conn:
        conn.execute("insert into activation_code(code_hash, audience) values (%s, 'student')", (hash_code(code),))
    print(code)


if __name__ == "__main__":
    main()
