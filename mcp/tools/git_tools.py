"""Local git subprocess tools. Full parameter docs: project skill."""
import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

from config import GIT_WORKDIR, log
from git_helpers import _auth_url, _git, _repo_path
from mcp_app import mcp


@mcp.tool()
def git_clone(repo_full_name: str, local_name: str = None, branch: str = None) -> Dict:
    """Clone from Gitea auth URL into workdir; fails if folder exists."""
    Path(GIT_WORKDIR).mkdir(parents=True, exist_ok=True)
    name = local_name or repo_full_name.split('/')[-1]
    dest = _repo_path(name)
    if Path(dest).exists():
        return {'error': f'Directory already exists: {dest}. Use git_pull to update or choose a different local_name.'}
    url = _auth_url(repo_full_name)
    args = ['clone', url, dest]
    if branch:
        args = ['clone', '-b', branch, url, dest]
    env = os.environ.copy()
    env['GIT_TERMINAL_PROMPT'] = '0'
    result = subprocess.run(['git'] + args, capture_output=True, text=True, env=env, timeout=120)
    if result.returncode != 0:
        return {'error': result.stderr.strip() or result.stdout.strip()}
    r = _git(dest, ['log', '--oneline', '-5'])
    return {'success': True, 'local_path': dest, 'repo': repo_full_name, 'recent_commits': r.get('output', '')}


@mcp.tool()
def git_init(local_name: str, repo_full_name: str = None) -> Dict:
    """git init + optional origin owner/repo."""
    Path(GIT_WORKDIR).mkdir(parents=True, exist_ok=True)
    dest = _repo_path(local_name)
    if Path(dest).exists():
        return {'error': f'Directory already exists: {dest}'}
    Path(dest).mkdir(parents=True)
    r = _git(dest, ['init'])
    if 'error' in r:
        return r
    if repo_full_name:
        url = _auth_url(repo_full_name)
        _git(dest, ['remote', 'add', 'origin', url])
    return {'success': True, 'local_path': dest, 'remote': repo_full_name or None}


@mcp.tool()
def git_status(local_name: str) -> Dict:
    """Parsed short status + current branch."""
    dest = _repo_path(local_name)
    r = _git(dest, ['status', '--short'])
    b = _git(dest, ['branch', '--show-current'])
    if 'error' in r:
        return r
    lines = r.get('output', '').splitlines()
    staged = [l[3:] for l in lines if l[:2] in ('A ', 'M ', 'D ', 'R ')]
    unstaged = [l[3:] for l in lines if l[1:2] in ('M', 'D') and l[0] == ' ']
    untracked = [l[3:] for l in lines if l[:2] == '??']
    return {
        'local_path': dest,
        'branch': b.get('output', ''),
        'staged': staged,
        'unstaged': unstaged,
        'untracked': untracked,
        'clean': len(lines) == 0
    }


@mcp.tool()
def git_write_file(local_name: str, filepath: str, content: str) -> Dict:
    """Write utf-8 file under repo (mkdir -p parents)."""
    dest = Path(_repo_path(local_name))
    if not dest.exists():
        return {'error': f'Repo not found: {local_name}. Use git_clone or git_init first.'}
    target = dest / filepath
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding='utf-8')
    return {'success': True, 'local_path': str(target), 'size': len(content)}


@mcp.tool()
def git_read_file(local_name: str, filepath: str) -> Dict:
    """Read utf-8 file from repo."""
    dest = Path(_repo_path(local_name))
    target = dest / filepath
    if not target.exists():
        return {'error': f'File not found: {filepath}'}
    if not target.is_file():
        return {'error': f'Not a file: {filepath}'}
    content = target.read_text(encoding='utf-8', errors='replace')
    return {'filepath': filepath, 'size': len(content), 'content': content}


@mcp.tool()
def git_delete_file(local_name: str, filepath: str) -> Dict:
    """Unlink working-tree file only."""
    dest = Path(_repo_path(local_name))
    target = dest / filepath
    if not target.exists():
        return {'error': f'File not found: {filepath}'}
    target.unlink()
    return {'success': True, 'deleted': filepath}


@mcp.tool()
def git_copy_file(src_local_name: str, src_path: str, dest_local_name: str, dest_path: str) -> Dict:
    """Server-side copy between clone dirs (no network)."""
    src = Path(_repo_path(src_local_name)) / src_path
    dest = Path(_repo_path(dest_local_name)) / dest_path
    if not src.exists():
        return {'error': f'Source file not found: {src_path}'}
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return {'success': True, 'src': str(src), 'dest': str(dest), 'size': dest.stat().st_size}


@mcp.tool()
def git_clone_to(src_local_name: str, dest_local_name: str, new_remote: str = None) -> Dict:
    """shutil.copytree clone; optional origin URL."""
    src = Path(_repo_path(src_local_name))
    dest = Path(_repo_path(dest_local_name))
    if not src.exists():
        return {'error': f'Source repo not found: {src_local_name}'}
    if dest.exists():
        return {'error': f'Destination already exists: {dest_local_name}'}
    shutil.copytree(src, dest)
    if new_remote:
        r = _git(str(dest), ['remote', 'set-url', 'origin', new_remote])
        if 'error' in r:
            return r
    remote_r = _git(str(dest), ['remote', 'get-url', 'origin'])
    return {'success': True, 'src': str(src), 'dest': str(dest), 'remote': remote_r.get('output', 'none')}


@mcp.tool()
def git_list_local_files(local_name: str, subpath: str = '') -> Dict:
    """One-level listing; hides .git."""
    dest = Path(_repo_path(local_name))
    target = dest / subpath if subpath else dest
    if not target.exists():
        return {'error': f'Path not found: {subpath or "root"}'}
    items = []
    for p in sorted(target.iterdir()):
        if p.name == '.git':
            continue
        items.append({'name': p.name, 'type': 'dir' if p.is_dir() else 'file', 'size': p.stat().st_size if p.is_file() else None})
    return {'local_path': str(target), 'count': len(items), 'items': items}


@mcp.tool()
def git_add(local_name: str, paths: List[str] = None) -> Dict:
    """git add paths or -A; returns git_status."""
    dest = _repo_path(local_name)
    args = ['add'] + (paths if paths else ['-A'])
    r = _git(dest, args)
    if 'error' in r:
        return r
    return git_status(local_name)


@mcp.tool()
def git_commit(local_name: str, message: str, add_all: bool = True) -> Dict:
    """Optional add -A then commit -m."""
    dest = _repo_path(local_name)
    if add_all:
        ra = _git(dest, ['add', '-A'])
        if 'error' in ra:
            return ra
    r = _git(dest, ['commit', '-m', message])
    if 'error' in r:
        return r
    sha = _git(dest, ['rev-parse', 'HEAD'])
    return {'success': True, 'commit_sha': sha.get('output', ''), 'message': message, 'output': r.get('output', '')}


@mcp.tool()
def git_push(local_name: str, branch: str = None, force: bool = False) -> Dict:
    """git push origin branch (default current)."""
    dest = _repo_path(local_name)
    if not branch:
        b = _git(dest, ['branch', '--show-current'])
        branch = b.get('output', 'main')
    args = ['push', 'origin', branch]
    if force:
        args.append('--force')
    r = _git(dest, args)
    if 'error' in r:
        return r
    return {'success': True, 'pushed_branch': branch, 'output': r.get('output', '') or r.get('stderr', '')}


@mcp.tool()
def git_pull(local_name: str, branch: str = None) -> Dict:
    """git pull origin [branch]."""
    dest = _repo_path(local_name)
    args = ['pull', 'origin'] + ([branch] if branch else [])
    r = _git(dest, args)
    if 'error' in r:
        return r
    return {'success': True, 'output': r.get('output', '') or r.get('stderr', '')}


@mcp.tool()
def git_log(local_name: str, limit: int = 10, branch: str = None) -> Dict:
    """Structured last N commits."""
    dest = _repo_path(local_name)
    args = ['log', f'--max-count={limit}', '--pretty=format:%H|%an|%ae|%ai|%s']
    if branch:
        args.append(branch)
    r = _git(dest, args)
    if 'error' in r:
        return r
    commits = []
    for line in r.get('output', '').splitlines():
        parts = line.split('|', 4)
        if len(parts) == 5:
            commits.append({'sha': parts[0][:12], 'full_sha': parts[0], 'author': parts[1], 'email': parts[2], 'date': parts[3], 'message': parts[4]})
    return {'local_path': _repo_path(local_name), 'commit_count': len(commits), 'commits': commits}


@mcp.tool()
def git_diff(local_name: str, filepath: str = None, staged: bool = False) -> Dict:
    """diff [--cached] [-- path]."""
    dest = _repo_path(local_name)
    args = ['diff']
    if staged:
        args.append('--cached')
    if filepath:
        args += ['--', filepath]
    r = _git(dest, args)
    if 'error' in r:
        return r
    return {'output': r.get('output', '(no changes)'), 'filepath': filepath or 'all'}


@mcp.tool()
def git_branch(local_name: str, create: str = None, delete: str = None) -> Dict:
    """List, or checkout -b create, or -d delete."""
    dest = _repo_path(local_name)
    if create:
        r = _git(dest, ['checkout', '-b', create])
        return r if 'error' in r else {'success': True, 'created_branch': create, 'output': r.get('output', '')}
    if delete:
        r = _git(dest, ['branch', '-d', delete])
        return r if 'error' in r else {'success': True, 'deleted_branch': delete}
    r = _git(dest, ['branch', '-a'])
    if 'error' in r:
        return r
    branches = [b.strip().lstrip('* ') for b in r.get('output', '').splitlines() if b.strip()]
    current = _git(dest, ['branch', '--show-current']).get('output', '')
    return {'current': current, 'branches': branches}


@mcp.tool()
def git_checkout(local_name: str, branch: str) -> Dict:
    """git checkout branch."""
    dest = _repo_path(local_name)
    r = _git(dest, ['checkout', branch])
    if 'error' in r:
        return r
    return {'success': True, 'branch': branch}


@mcp.tool()
def git_list_repos() -> Dict:
    """Scan workdir for .git dirs."""
    base = Path(GIT_WORKDIR)
    if not base.exists():
        return {'count': 0, 'repos': []}
    repos = []
    for p in sorted(base.iterdir()):
        if p.is_dir() and (p / '.git').exists():
            b = _git(str(p), ['branch', '--show-current']).get('output', '')
            log_r = _git(str(p), ['log', '-1', '--pretty=format:%h %s']).get('output', '')
            repos.append({'name': p.name, 'path': str(p), 'branch': b, 'last_commit': log_r})
    return {'count': len(repos), 'workdir': GIT_WORKDIR, 'repos': repos}


@mcp.tool()
def git_remove_local(local_name: str) -> Dict:
    """rm -rf local clone only."""
    dest = Path(_repo_path(local_name))
    if not dest.exists():
        return {'error': f'Local repo not found: {local_name}'}
    shutil.rmtree(dest)
    return {'success': True, 'removed': str(dest)}

