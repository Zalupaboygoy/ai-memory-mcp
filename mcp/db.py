"""PostgreSQL connection and token resolution."""
import hashlib

import psycopg2

from config import DB_CONFIG


def get_conn():
    return psycopg2.connect(**DB_CONFIG)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _resolve_token(token: str):
    token_hash = _hash_token(token)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT t.user_id, u.is_admin
                FROM tokens t
                JOIN users u ON u.id = t.user_id
                WHERE t.token_hash = %s
                  AND (t.expires_at IS NULL OR t.expires_at > NOW())
            """, (token_hash,))
            row = cur.fetchone()
            return (row[0], row[1]) if row else (None, False)
    finally:
        conn.close()
