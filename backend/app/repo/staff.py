"""Staff accounts: reviewers, admins, ministry viewers."""


def get(conn, staff_id: int) -> dict | None:
    return conn.execute("select * from staff_user where id = %s", (staff_id,)).fetchone()


def find_by_email(conn, email: str) -> dict | None:
    return conn.execute("select * from staff_user where email = %s", (email,)).fetchone()


def create(conn, email: str, password_hash: str, display_name: str, role: str) -> int:
    return conn.execute(
        "insert into staff_user(email, password_hash, display_name, role) values (%s, %s, %s, %s) returning id",
        (email, password_hash, display_name, role)).fetchone()["id"]
