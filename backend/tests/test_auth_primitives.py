"""Hashing of tokens, activation codes and passwords, and the tables behind sign-in."""
import psycopg
import pytest

from app.auth.passwords import hash_password, verify_password
from app.auth.secrets import hash_code, hash_token, new_token


def test_tokens_are_long_random_and_prefixed():
    a, b = new_token("at"), new_token("rt")
    assert a.startswith("at_") and b.startswith("rt_") and len(a) >= 40 and a[3:] != b[3:]
    assert new_token("at") != a


def test_only_a_digest_is_stored():
    token = new_token("at")
    digest = hash_token(token)
    assert len(digest) == 64 and token not in digest and hash_token(token) == digest


@pytest.mark.parametrize("typed", ["DEMO-0001", "demo-0001", "  Demo-0001 ", "DEMO-0001\n"])
def test_a_code_typed_on_a_phone_hashes_the_same(typed):
    assert hash_code(typed) == hash_code("DEMO-0001")


def test_different_codes_hash_differently():
    assert hash_code("DEMO-0001") != hash_code("DEMO-0002")


def test_password_round_trip():
    stored = hash_password("mật khẩu thử")
    assert stored.startswith("$argon2") and verify_password("mật khẩu thử", stored)
    assert not verify_password("sai", stored)


@pytest.mark.parametrize("stored", ["!", "", "not-a-hash"])
def test_an_unusable_stored_value_never_matches_and_never_raises(stored):
    assert verify_password("anything", stored) is False


def test_a_token_needs_its_family(conn):
    with pytest.raises(psycopg.errors.NotNullViolation):
        conn.execute("insert into auth_token(token_hash, subject_type, subject_id, kind, expires_at) "
                     "values ('h', 'learner', 1, 'access', now())")


def test_pseudonyms_come_from_a_sequence(conn):
    first = conn.execute("select nextval('learner_pseudonym_seq') as n").fetchone()["n"]
    assert first >= 1000


def test_failed_sign_ins_are_typed(conn):
    conn.execute("insert into auth_failure(ip, kind, at) values ('1.2.3.4', 'activate', now())")
    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute("insert into auth_failure(ip, kind, at) values ('1.2.3.4', 'guess', now())")
