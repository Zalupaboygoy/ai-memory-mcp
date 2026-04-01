#!/usr/bin/env python3
"""
AI Memory Admin UI
Simple web interface for managing users and tokens.
"""

import os
import hashlib
import secrets
from typing import Optional
from datetime import datetime, timedelta
from functools import wraps

import psycopg2
import psycopg2.extras
from fastapi import FastAPI, Request, Form, Cookie, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'postgres'),
    'port': int(os.getenv('DB_PORT', 5432)),
    'dbname': os.getenv('DB_NAME', 'ai_memory'),
    'user': os.getenv('DB_USER', 'mcpuser'),
    'password': os.getenv('DB_PASSWORD', ''),
}


def get_conn():
    return psycopg2.connect(**DB_CONFIG)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _validate_admin_token(token: str) -> Optional[dict]:
    if not token:
        return None
    token_hash = _hash_token(token)
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT u.id, u.username, u.is_admin
                FROM tokens t
                JOIN users u ON u.id = t.user_id
                WHERE t.token_hash = %s
                  AND u.is_admin = TRUE
                  AND (t.expires_at IS NULL OR t.expires_at > NOW())
            """, (token_hash,))
            return cur.fetchone()
    finally:
        conn.close()


CSS = """
body{font-family:system-ui,sans-serif;max-width:960px;margin:0 auto;padding:20px;background:#f5f5f5;color:#333}
h1{color:#1a1a2e;border-bottom:2px solid #4a90d9;padding-bottom:8px}
h2{color:#1a1a2e;margin-top:32px}
table{width:100%;border-collapse:collapse;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 1px 4px rgba(0,0,0,.1)}
th{background:#4a90d9;color:#fff;padding:10px 14px;text-align:left;font-weight:600}
td{padding:9px 14px;border-bottom:1px solid #eee}
tr:last-child td{border-bottom:none}
tr:hover td{background:#f0f7ff}
.btn{display:inline-block;padding:7px 16px;border-radius:5px;border:none;cursor:pointer;font-size:14px;text-decoration:none}
.btn-primary{background:#4a90d9;color:#fff}
.btn-danger{background:#e74c3c;color:#fff}
.btn-success{background:#27ae60;color:#fff}
.btn:hover{opacity:.85}
form.inline{display:inline}
input[type=text],input[type=password],input[type=number]{padding:8px 12px;border:1px solid #ccc;border-radius:5px;font-size:14px;width:220px}
.card{background:#fff;border-radius:8px;padding:24px;box-shadow:0 1px 4px rgba(0,0,0,.1);margin-bottom:20px}
.token-box{font-family:monospace;background:#1a1a2e;color:#50fa7b;padding:12px;border-radius:5px;word-break:break-all;margin:10px 0}
.alert{padding:12px 16px;border-radius:5px;margin:12px 0}
.alert-success{background:#d4edda;color:#155724;border:1px solid #c3e6cb}
.alert-danger{background:#f8d7da;color:#721c24;border:1px solid #f5c6cb}
.badge{display:inline-block;padding:2px 8px;border-radius:12px;font-size:12px;font-weight:600}
.badge-admin{background:#ffd700;color:#333}
.badge-active{background:#d4edda;color:#155724}
.badge-expired{background:#f8d7da;color:#721c24}
nav{display:flex;gap:12px;margin-bottom:24px;padding:12px 0;border-bottom:1px solid #ddd}
nav a{text-decoration:none;color:#4a90d9;font-weight:500}
nav a:hover{text-decoration:underline}
.login-card{max-width:400px;margin:80px auto}
"""


def _page(title: str, body: str, nav: bool = True) -> str:
    nav_html = ""
    if nav:
        nav_html = """<nav>
            <a href="/">Dashboard</a>
            <a href="/users">Users</a>
            <a href="/logout">Logout</a>
        </nav>"""
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{title} — AI Memory Admin</title>
<style>{CSS}</style></head>
<body>
<h1>AI Memory Admin</h1>
{nav_html}
{body}
</body></html>"""


app = FastAPI(title="AI Memory Admin")


def _get_user(request: Request) -> Optional[dict]:
    token = request.cookies.get('admin_token', '')
    return _validate_admin_token(token)


@app.get('/', response_class=HTMLResponse)
def dashboard(request: Request):
    user = _get_user(request)
    if not user:
        return RedirectResponse('/login', status_code=302)
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT COUNT(*) as c FROM users")
            user_count = cur.fetchone()['c']
            cur.execute("SELECT COUNT(*) as c FROM tokens WHERE expires_at IS NULL OR expires_at > NOW()")
            token_count = cur.fetchone()['c']
            cur.execute("SELECT COUNT(*) as c FROM entries")
            entry_count = cur.fetchone()['c']
            cur.execute("SELECT COUNT(*) as c FROM relations")
            rel_count = cur.fetchone()['c']
    finally:
        conn.close()
    body = f"""
    <div class="card">
        <p>Logged in as <strong>{user['username']}</strong> <span class="badge badge-admin">admin</span></p>
    </div>
    <h2>System Overview</h2>
    <table>
        <tr><th>Metric</th><th>Value</th></tr>
        <tr><td>Total Users</td><td>{user_count}</td></tr>
        <tr><td>Active Tokens</td><td>{token_count}</td></tr>
        <tr><td>Total Entries</td><td>{entry_count}</td></tr>
        <tr><td>Graph Relations</td><td>{rel_count}</td></tr>
    </table>
    <div style="margin-top:20px">
        <a href="/users" class="btn btn-primary">Manage Users</a>
    </div>
    """
    return HTMLResponse(_page('Dashboard', body))


@app.get('/login', response_class=HTMLResponse)
def login_get(request: Request, error: str = ''):
    err = f'<div class="alert alert-danger">{error}</div>' if error else ''
    body = f"""
    <div class="card login-card">
        <h2 style="margin-top:0">Login</h2>
        <p>Enter your admin token to access the admin panel.</p>
        {err}
        <form method="post" action="/login">
            <div style="margin-bottom:12px">
                <input type="password" name="token" placeholder="Bearer token" style="width:100%;box-sizing:border-box" required autofocus>
            </div>
            <button type="submit" class="btn btn-primary" style="width:100%">Login</button>
        </form>
    </div>
    """
    return HTMLResponse(_page('Login', body, nav=False))


@app.post('/login')
def login_post(response: Response, token: str = Form(...)):
    user = _validate_admin_token(token)
    if not user:
        return RedirectResponse('/login?error=Invalid+or+non-admin+token', status_code=302)
    resp = RedirectResponse('/', status_code=302)
    resp.set_cookie('admin_token', token, httponly=True, samesite='lax', max_age=28800)
    return resp


@app.get('/logout')
def logout():
    resp = RedirectResponse('/login', status_code=302)
    resp.delete_cookie('admin_token')
    return resp


@app.get('/users', response_class=HTMLResponse)
def users_list(request: Request, msg: str = '', err: str = ''):
    user = _get_user(request)
    if not user:
        return RedirectResponse('/login', status_code=302)
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT u.id, u.username, u.is_admin, u.created_at,
                       COUNT(DISTINCT t.id) FILTER (WHERE t.expires_at IS NULL OR t.expires_at > NOW()) as active_tokens,
                       COUNT(DISTINCT e.id) as entry_count
                FROM users u
                LEFT JOIN tokens t ON t.user_id = u.id
                LEFT JOIN entries e ON e.user_id = u.id
                GROUP BY u.id ORDER BY u.id
            """)
            users = cur.fetchall()
    finally:
        conn.close()

    msg_html = f'<div class="alert alert-success">{msg}</div>' if msg else ''
    err_html = f'<div class="alert alert-danger">{err}</div>' if err else ''

    rows = ''
    for u in users:
        admin_badge = '<span class="badge badge-admin">admin</span>' if u['is_admin'] else ''
        token_link = f'<a href="/users/{u["id"]}/tokens" class="btn btn-primary" style="padding:4px 10px;font-size:12px">Tokens ({u["active_tokens"]})</a>'
        delete_btn = ''
        if u['id'] != user['id']:
            delete_btn = f'''<form class="inline" method="post" action="/users/{u['id']}/delete" onsubmit="return confirm('Delete user {u['username']}?')">
                <button type="submit" class="btn btn-danger" style="padding:4px 10px;font-size:12px">Delete</button>
            </form>'''
        rows += f"""<tr>
            <td>{u['id']}</td>
            <td>{u['username']} {admin_badge}</td>
            <td>{u['entry_count']}</td>
            <td>{str(u['created_at'])[:10]}</td>
            <td>{token_link} {delete_btn}</td>
        </tr>"""

    body = f"""
    {msg_html}{err_html}
    <h2>Users</h2>
    <table>
        <tr><th>ID</th><th>Username</th><th>Entries</th><th>Created</th><th>Actions</th></tr>
        {rows}
    </table>
    <h2>Create New User</h2>
    <div class="card">
        <form method="post" action="/users/create">
            <input type="text" name="username" placeholder="Username" required>
            <label style="margin-left:12px">
                <input type="checkbox" name="is_admin"> Admin
            </label>
            <button type="submit" class="btn btn-success" style="margin-left:12px">Create User</button>
        </form>
    </div>
    """
    return HTMLResponse(_page('Users', body))


@app.post('/users/create')
def create_user(request: Request, username: str = Form(...), is_admin: Optional[str] = Form(None)):
    user = _get_user(request)
    if not user:
        return RedirectResponse('/login', status_code=302)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (username, is_admin) VALUES (%s, %s)",
                (username, is_admin == 'on')
            )
            conn.commit()
        return RedirectResponse(f'/users?msg=User+{username}+created+successfully', status_code=302)
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        return RedirectResponse(f'/users?err=Username+{username}+already+exists', status_code=302)
    except Exception as e:
        conn.rollback()
        return RedirectResponse(f'/users?err={str(e)}', status_code=302)
    finally:
        conn.close()


@app.post('/users/{user_id}/delete')
def delete_user(request: Request, user_id: int):
    user = _get_user(request)
    if not user:
        return RedirectResponse('/login', status_code=302)
    if user_id == user['id']:
        return RedirectResponse('/users?err=Cannot+delete+yourself', status_code=302)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM users WHERE id = %s RETURNING username", (user_id,))
            row = cur.fetchone()
            if not row:
                return RedirectResponse('/users?err=User+not+found', status_code=302)
            conn.commit()
        return RedirectResponse(f'/users?msg=User+deleted', status_code=302)
    except Exception as e:
        conn.rollback()
        return RedirectResponse(f'/users?err={str(e)}', status_code=302)
    finally:
        conn.close()


FLASH_TOKEN_COOKIE = 'admin_new_token_flash'


@app.get('/users/{user_id}/tokens', response_class=HTMLResponse)
def user_tokens(request: Request, user_id: int, msg: str = '', err: str = ''):
    user = _get_user(request)
    if not user:
        return RedirectResponse('/login', status_code=302)
    # One-time display: token was set as HttpOnly cookie on POST (never in URL / logs)
    new_token = request.cookies.get(FLASH_TOKEN_COOKIE, '')
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT id, username, is_admin FROM users WHERE id = %s", (user_id,))
            target = cur.fetchone()
            if not target:
                return RedirectResponse('/users?err=User+not+found', status_code=302)
            cur.execute("""
                SELECT id, name, created_at, expires_at,
                       (expires_at IS NULL OR expires_at > NOW()) as is_active
                FROM tokens WHERE user_id = %s ORDER BY created_at DESC
            """, (user_id,))
            tokens = cur.fetchall()
    finally:
        conn.close()

    msg_html = f'<div class="alert alert-success">{msg}</div>' if msg else ''
    err_html = f'<div class="alert alert-danger">{err}</div>' if err else ''
    new_token_html = ''
    if new_token:
        new_token_html = f"""
        <div class="alert alert-success">
            <strong>New token created!</strong> Copy it now — it will never be shown again:<br>
            <div class="token-box">{new_token}</div>
        </div>"""

    rows = ''
    for t in tokens:
        active_badge = '<span class="badge badge-active">active</span>' if t['is_active'] else '<span class="badge badge-expired">expired</span>'
        expires = str(t['expires_at'])[:16] if t['expires_at'] else 'never'
        rows += f"""<tr>
            <td>{t['id']}</td>
            <td>{t['name']}</td>
            <td>{active_badge}</td>
            <td>{str(t['created_at'])[:16]}</td>
            <td>{expires}</td>
            <td>
                <form class="inline" method="post" action="/tokens/{t['id']}/revoke?user_id={user_id}" onsubmit="return confirm('Revoke token {t['name']}?')">
                    <button type="submit" class="btn btn-danger" style="padding:4px 10px;font-size:12px">Revoke</button>
                </form>
            </td>
        </tr>"""

    body = f"""
    {msg_html}{err_html}{new_token_html}
    <h2>Tokens for {target['username']}</h2>
    <table>
        <tr><th>ID</th><th>Name</th><th>Status</th><th>Created</th><th>Expires</th><th>Actions</th></tr>
        {rows if rows else '<tr><td colspan="6" style="text-align:center;color:#888">No tokens</td></tr>'}
    </table>
    <h2>Create New Token</h2>
    <div class="card">
        <form method="post" action="/users/{user_id}/tokens/create">
            <input type="text" name="token_name" placeholder="Token name (e.g. claude-desktop)" required>
            <input type="number" name="expires_days" placeholder="Expires in days (empty=never)" min="1" style="width:160px;margin-left:8px">
            <button type="submit" class="btn btn-success" style="margin-left:8px">Create Token</button>
        </form>
    </div>
    <div style="margin-top:16px">
        <a href="/users" class="btn btn-primary">← Back to Users</a>
    </div>
    """
    response = HTMLResponse(_page(f'Tokens — {target["username"]}', body))
    if new_token:
        response.delete_cookie(FLASH_TOKEN_COOKIE, path='/')
    return response


@app.post('/users/{user_id}/tokens/create')
def create_token(request: Request, user_id: int, token_name: str = Form(...), expires_days: Optional[int] = Form(None)):
    user = _get_user(request)
    if not user:
        return RedirectResponse('/login', status_code=302)
    token_value = secrets.token_hex(32)
    token_hash = hashlib.sha256(token_value.encode()).hexdigest()
    expires_at = None
    if expires_days and expires_days > 0:
        expires_at = datetime.utcnow() + timedelta(days=expires_days)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO tokens (user_id, token_hash, name, expires_at) VALUES (%s, %s, %s, %s)",
                (user_id, token_hash, token_name, expires_at)
            )
            conn.commit()
        resp = RedirectResponse(f'/users/{user_id}/tokens?msg=Token+created', status_code=302)
        resp.set_cookie(
            FLASH_TOKEN_COOKIE,
            token_value,
            max_age=120,
            httponly=True,
            samesite='lax',
            path='/',
        )
        return resp
    except Exception as e:
        conn.rollback()
        return RedirectResponse(f'/users/{user_id}/tokens?err={str(e)}', status_code=302)
    finally:
        conn.close()


@app.post('/tokens/{token_id}/revoke')
def revoke_token(request: Request, token_id: int, user_id: int):
    user = _get_user(request)
    if not user:
        return RedirectResponse('/login', status_code=302)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM tokens WHERE id = %s RETURNING id", (token_id,))
            if not cur.fetchone():
                return RedirectResponse(f'/users/{user_id}/tokens?err=Token+not+found', status_code=302)
            conn.commit()
        return RedirectResponse(f'/users/{user_id}/tokens?msg=Token+revoked', status_code=302)
    except Exception as e:
        conn.rollback()
        return RedirectResponse(f'/users/{user_id}/tokens?err={str(e)}', status_code=302)
    finally:
        conn.close()


if __name__ == '__main__':
    import uvicorn
    host = os.getenv('ADMIN_HOST', '0.0.0.0')
    port = int(os.getenv('ADMIN_PORT', 8080))
    uvicorn.run(app, host=host, port=port)
