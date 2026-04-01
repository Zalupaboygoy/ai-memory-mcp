"""Gitea REST wrappers. Full contract: project skill."""
import base64
from typing import Dict, Optional

import requests

from config import GITEA_URL
from gitea_client import _gdel, _gget, _gpost, _gput, _gh
from mcp_app import mcp

@mcp.tool()
def gitea_create_repo(name: str, description: str = '', private: bool = True, auto_init: bool = True, default_branch: str = 'main') -> Dict:
    """POST /user/repos (service user token)."""
    r = _gpost('/user/repos', {'name': name, 'description': description, 'private': private, 'auto_init': auto_init, 'default_branch': default_branch})
    if 'error' in r:
        return r
    return {'success': True, 'id': r.get('id'), 'full_name': r.get('full_name'), 'html_url': r.get('html_url'), 'clone_url': r.get('clone_url'), 'ssh_url': r.get('ssh_url'), 'private': r.get('private')}


@mcp.tool()
def gitea_list_repos(limit: int = 20) -> Dict:
    """GET /user/repos."""
    r = _gget(f'/user/repos?limit={limit}&sort=updated')
    if 'error' in r:
        return r
    repos = r.get('data', []) if isinstance(r, dict) else r
    return {'count': len(repos), 'repos': [{'full_name': x.get('full_name'), 'description': x.get('description'), 'html_url': x.get('html_url'), 'private': x.get('private'), 'updated_at': x.get('updated')} for x in repos]}


@mcp.tool()
def gitea_get_repo_info(owner: str, repo: str) -> Dict:
    """GET /repos/{owner}/{repo}."""
    r = _gget(f'/repos/{owner}/{repo}')
    if 'error' in r:
        return r
    return {'full_name': r.get('full_name'), 'description': r.get('description'), 'html_url': r.get('html_url'), 'clone_url': r.get('clone_url'), 'ssh_url': r.get('ssh_url'), 'private': r.get('private'), 'default_branch': r.get('default_branch'), 'stars': r.get('stars_count'), 'open_issues': r.get('open_issues_count'), 'updated_at': r.get('updated')}


@mcp.tool()
def gitea_list_files(owner: str, repo: str, path: str = '', ref: str = 'main') -> Dict:
    """GET contents API; path directory listing."""
    r = _gget(f'/repos/{owner}/{repo}/contents/{path}?ref={ref}')
    if isinstance(r, dict) and 'error' in r:
        return r
    if not isinstance(r, list):
        return {'error': 'Not a directory or path not found'}
    return {'path': path or '/', 'count': len(r), 'items': [{'name': f.get('name'), 'type': f.get('type'), 'path': f.get('path'), 'size': f.get('size')} for f in r]}


@mcp.tool()
def gitea_get_file(owner: str, repo: str, filepath: str, ref: str = 'main') -> Dict:
    """GET file; returns sha for updates."""
    r = _gget(f'/repos/{owner}/{repo}/contents/{filepath}?ref={ref}')
    if 'error' in r:
        return r
    content = base64.b64decode(r.get('content', '')).decode('utf-8', errors='replace') if r.get('content') else ''
    return {'path': r.get('path'), 'name': r.get('name'), 'size': r.get('size'), 'sha': r.get('sha'), 'content': content, 'html_url': r.get('html_url')}


@mcp.tool()
def gitea_create_or_update_file(owner: str, repo: str, filepath: str, content: str, message: str, branch: str = 'main', sha: Optional[str] = None) -> Dict:
    """PUT contents; sha required to overwrite existing blob."""
    data = {'message': message, 'content': base64.b64encode(content.encode()).decode(), 'branch': branch}
    if sha:
        data['sha'] = sha
    r = _gput(f'/repos/{owner}/{repo}/contents/{filepath}', data)
    if 'error' in r:
        return r
    if 'content' not in r:
        return {'error': r.get('message', str(r))}
    return {'success': True, 'filepath': filepath, 'commit_sha': r.get('commit', {}).get('sha'), 'html_url': r.get('content', {}).get('html_url')}


@mcp.tool()
def gitea_delete_file(owner: str, repo: str, filepath: str, message: str, sha: str, branch: str = 'main') -> Dict:
    """DELETE contents with sha + message."""
    return _gdel(f'/repos/{owner}/{repo}/contents/{filepath}', {'message': message, 'sha': sha, 'branch': branch})


@mcp.tool()
def gitea_create_issue(owner: str, repo: str, title: str, body: str = '') -> Dict:
    """POST issue."""
    r = _gpost(f'/repos/{owner}/{repo}/issues', {'title': title, 'body': body})
    if 'error' in r:
        return r
    return {'success': True, 'issue_number': r.get('number'), 'title': r.get('title'), 'html_url': r.get('html_url'), 'state': r.get('state')}


@mcp.tool()
def gitea_search_repos(query: str, limit: int = 10) -> Dict:
    """GET /repos/search."""
    r = _gget(f'/repos/search?q={query}&limit={limit}&sort=updated')
    if 'error' in r:
        return r
    repos = r.get('data', [])
    return {'query': query, 'count': len(repos), 'repos': [{'full_name': x.get('full_name'), 'description': x.get('description'), 'html_url': x.get('html_url'), 'private': x.get('private'), 'owner': x.get('owner', {}).get('login')} for x in repos]}


@mcp.tool()
def gitea_transfer_repo(owner: str, repo: str, new_owner: str) -> Dict:
    """POST transfer."""
    r = _gpost(f'/repos/{owner}/{repo}/transfer', {'new_owner': new_owner})
    if 'error' in r:
        return r
    return {'success': True, 'full_name': r.get('full_name'), 'html_url': r.get('html_url'), 'owner': r.get('owner', {}).get('login')}


@mcp.tool()
def gitea_add_collaborator(owner: str, repo: str, username: str, permission: str = 'write') -> Dict:
    """PUT collaborator permission."""
    r = _gput(f'/repos/{owner}/{repo}/collaborators/{username}', {'permission': permission})
    return {'success': True, 'collaborator': username, 'permission': permission} if r.get('success') or not r.get('error') else r


@mcp.tool()
def gitea_remove_collaborator(owner: str, repo: str, username: str) -> Dict:
    """DELETE collaborator."""
    return _gdel(f'/repos/{owner}/{repo}/collaborators/{username}')


@mcp.tool()
def gitea_delete_repo(owner: str, repo: str) -> Dict:
    """DELETE repo (irreversible)."""
    return _gdel(f'/repos/{owner}/{repo}')


@mcp.tool()
def gitea_update_repo(owner: str, repo: str, description: str = None, private: bool = None, website: str = None, default_branch: str = None) -> Dict:
    """PATCH repo settings (partial)."""
    data = {}
    if description is not None: data['description'] = description
    if private is not None: data['private'] = private
    if website is not None: data['website'] = website
    if default_branch is not None: data['default_branch'] = default_branch
    if not data:
        return {'error': 'No fields to update'}
    r = requests.patch(f'{GITEA_URL}/api/v1/repos/{owner}/{repo}', headers=_gh(), json=data, timeout=10)
    if not r.ok:
        return {'error': r.text, 'status': r.status_code}
    d = r.json()
    return {'success': True, 'full_name': d.get('full_name'), 'private': d.get('private'), 'description': d.get('description'), 'default_branch': d.get('default_branch')}


@mcp.tool()
def gitea_fork_repo(owner: str, repo: str, fork_name: str = None) -> Dict:
    """POST /forks."""
    data = {}
    if fork_name:
        data['name'] = fork_name
    r = _gpost(f'/repos/{owner}/{repo}/forks', data)
    if 'error' in r:
        return r
    return {'success': True, 'full_name': r.get('full_name'), 'html_url': r.get('html_url'), 'clone_url': r.get('clone_url')}


@mcp.tool()
def gitea_list_branches(owner: str, repo: str) -> Dict:
    """GET branches."""
    r = _gget(f'/repos/{owner}/{repo}/branches')
    if isinstance(r, dict) and 'error' in r:
        return r
    branches = r if isinstance(r, list) else []
    return {'count': len(branches), 'branches': [{'name': b.get('name'), 'sha': b.get('commit', {}).get('id', '')[:12]} for b in branches]}


@mcp.tool()
def gitea_create_branch(owner: str, repo: str, branch_name: str, from_branch: str = 'main') -> Dict:
    """POST branch from ref."""
    r = _gpost(f'/repos/{owner}/{repo}/branches', {'new_branch_name': branch_name, 'old_branch_name': from_branch})
    if 'error' in r:
        return r
    return {'success': True, 'branch': r.get('name'), 'sha': r.get('commit', {}).get('id', '')}


@mcp.tool()
def gitea_delete_branch(owner: str, repo: str, branch_name: str) -> Dict:
    """DELETE branch."""
    return _gdel(f'/repos/{owner}/{repo}/branches/{branch_name}')


@mcp.tool()
def gitea_get_commits(owner: str, repo: str, branch: str = 'main', limit: int = 10) -> Dict:
    """GET commits list."""
    r = _gget(f'/repos/{owner}/{repo}/commits?sha={branch}&limit={limit}')
    if isinstance(r, dict) and 'error' in r:
        return r
    commits_raw = r if isinstance(r, list) else r.get('commits', [])
    commits = [{'sha': c.get('sha', '')[:12], 'author': c.get('commit', {}).get('author', {}).get('name'), 'date': c.get('commit', {}).get('author', {}).get('date'), 'message': c.get('commit', {}).get('message', '').split('\n')[0]} for c in commits_raw]
    return {'branch': branch, 'count': len(commits), 'commits': commits}


@mcp.tool()
def gitea_list_collaborators(owner: str, repo: str) -> Dict:
    """GET collaborators."""
    r = _gget(f'/repos/{owner}/{repo}/collaborators')
    if isinstance(r, dict) and 'error' in r:
        return r
    users = r if isinstance(r, list) else []
    return {'count': len(users), 'collaborators': [{'username': u.get('login'), 'email': u.get('email'), 'is_admin': u.get('is_admin')} for u in users]}


@mcp.tool()
def gitea_list_issues(owner: str, repo: str, state: str = 'open', limit: int = 20) -> Dict:
    """GET issues filtered by state."""
    r = _gget(f'/repos/{owner}/{repo}/issues?type=issues&state={state}&limit={limit}')
    if isinstance(r, dict) and 'error' in r:
        return r
    issues = r if isinstance(r, list) else []
    return {'count': len(issues), 'issues': [{'number': i.get('number'), 'title': i.get('title'), 'state': i.get('state'), 'html_url': i.get('html_url'), 'created_at': i.get('created_at')} for i in issues]}


@mcp.tool()
def gitea_close_issue(owner: str, repo: str, issue_number: int, comment: str = None) -> Dict:
    """Optional comment POST then PATCH state closed."""
    if comment:
        _gpost(f'/repos/{owner}/{repo}/issues/{issue_number}/comments', {'body': comment})
    r = requests.patch(f'{GITEA_URL}/api/v1/repos/{owner}/{repo}/issues/{issue_number}', headers=_gh(), json={'state': 'closed'}, timeout=10)
    if not r.ok:
        return {'error': r.text}
    return {'success': True, 'issue_number': issue_number, 'state': 'closed'}
