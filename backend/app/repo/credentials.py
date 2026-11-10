"""Private password credentials owned by Business, never readable by Chat."""


def by_username(conn, username):
    return conn.execute("select * from learner_credential where username=%s", (username,)).fetchone()


def by_learner(conn, learner_id):
    return conn.execute("select * from learner_credential where learner_id=%s", (learner_id,)).fetchone()


def create(conn, learner_id, username, password_hash):
    conn.execute("insert into learner_credential(learner_id,username,password_hash) values (%s,%s,%s)",
                 (learner_id, username, password_hash))


def change_password(conn, learner_id, password_hash, now):
    conn.execute("update learner_credential set password_hash=%s,changed_at=%s where learner_id=%s",
                 (password_hash, now, learner_id))


def delete(conn, learner_id):
    conn.execute("delete from learner_credential where learner_id=%s", (learner_id,))
