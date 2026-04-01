"""Low-level Gitea HTTP API helpers."""
import requests

from config import GITEA_TOKEN, GITEA_URL


def _gh():
    return {'Authorization': f'token {GITEA_TOKEN}', 'Content-Type': 'application/json'}


def _gget(path):
    r = requests.get(f'{GITEA_URL}/api/v1{path}', headers=_gh(), timeout=10)
    return r.json() if r.ok else {'error': r.text, 'status': r.status_code}


def _gpost(path, data):
    r = requests.post(f'{GITEA_URL}/api/v1{path}', headers=_gh(), json=data, timeout=10)
    return r.json() if r.ok else {'error': r.text, 'status': r.status_code}


def _gput(path, data):
    r = requests.put(f'{GITEA_URL}/api/v1{path}', headers=_gh(), json=data, timeout=10)
    return r.json() if r.ok else {'error': r.text, 'status': r.status_code}


def _gdel(path, data=None):
    r = requests.delete(f'{GITEA_URL}/api/v1{path}', headers=_gh(), json=data, timeout=10)
    if r.status_code == 204:
        return {'success': True}
    return r.json() if r.content else {'error': 'failed', 'status': r.status_code}
