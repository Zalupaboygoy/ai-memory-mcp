"""Low-level Gitea HTTP API helpers."""
import requests

from config import GITEA_TOKEN, GITEA_URL


def _gh():
    return {'Authorization': f'token {GITEA_TOKEN}', 'Content-Type': 'application/json'}


def _response_ok(r: requests.Response):
    """Parse HTTP response; 204 No Content and empty bodies must not call .json()."""
    if r.status_code == 204:
        return {'success': True}
    if not r.ok:
        return {'error': r.text, 'status': r.status_code}
    if not r.content or not r.content.strip():
        return {'success': True}
    try:
        return r.json()
    except ValueError:
        return {'success': True}


def _gget(path):
    r = requests.get(f'{GITEA_URL}/api/v1{path}', headers=_gh(), timeout=10)
    return _response_ok(r)


def _gpost(path, data):
    r = requests.post(f'{GITEA_URL}/api/v1{path}', headers=_gh(), json=data, timeout=10)
    return _response_ok(r)


def _gput(path, data):
    r = requests.put(f'{GITEA_URL}/api/v1{path}', headers=_gh(), json=data, timeout=10)
    return _response_ok(r)


def _gpatch(path, data):
    r = requests.patch(f'{GITEA_URL}/api/v1{path}', headers=_gh(), json=data, timeout=10)
    return _response_ok(r)


def _gdel(path, data=None):
    r = requests.delete(f'{GITEA_URL}/api/v1{path}', headers=_gh(), json=data, timeout=10)
    return _response_ok(r)
