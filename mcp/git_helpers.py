"""Local git subprocess helpers and authenticated clone URLs."""
import os
import shutil
import subprocess
import time
from pathlib import Path

from config import (
    GITEA_AGENT_LOGIN,
    GITEA_AGENT_TOKEN,
    GITEA_INTERNAL_URL,
    GIT_COMMIT_USER_EMAIL,
    GIT_COMMIT_USER_NAME,
    GIT_LOCAL_REPOS_TTL_DAYS,
    GIT_WORKDIR,
    log,
)


def git_command_env() -> dict:
    """Env for every git subprocess: no TTY prompts; author/committer if not set globally."""
    env = os.environ.copy()
    env['GIT_TERMINAL_PROMPT'] = '0'
    env.setdefault('GIT_AUTHOR_NAME', GIT_COMMIT_USER_NAME)
    env.setdefault('GIT_AUTHOR_EMAIL', GIT_COMMIT_USER_EMAIL)
    env.setdefault('GIT_COMMITTER_NAME', GIT_COMMIT_USER_NAME)
    env.setdefault('GIT_COMMITTER_EMAIL', GIT_COMMIT_USER_EMAIL)
    return env


def _git(repo_path: str, args: list, input_text: str = None) -> dict:
    path = Path(repo_path)
    if not path.exists():
        return {'error': f'Path does not exist: {repo_path}'}
    env = git_command_env()
    result = subprocess.run(
        ['git'] + args,
        cwd=str(path),
        capture_output=True,
        text=True,
        env=env,
        input=input_text,
        timeout=60
    )
    out = result.stdout.strip()
    err = result.stderr.strip()
    if result.returncode != 0:
        return {'error': err or out, 'returncode': result.returncode}
    return {'success': True, 'output': out, 'stderr': err}


def _repo_path(name: str) -> str:
    safe = name.replace('..', '').replace('/', '-').strip('-')
    return str(Path(GIT_WORKDIR) / safe)


def _auth_url(repo_full_name: str) -> str:
    base = GITEA_INTERNAL_URL.rstrip('/')
    return f"{base.replace('://', f'://{GITEA_AGENT_LOGIN}:{GITEA_AGENT_TOKEN}@')}/{repo_full_name}.git"


def _repo_last_activity_ts(repo: Path) -> float:
    """Approximate last activity from mtimes under .git."""
    git = repo / '.git'
    if not git.exists():
        return 0.0
    if git.is_file():
        return repo.stat().st_mtime
    max_t = max(git.stat().st_mtime, repo.stat().st_mtime)
    n = 0
    for root, _dirs, files in os.walk(git):
        max_t = max(max_t, os.path.getmtime(root))
        for f in files:
            if n >= 15000:
                return max_t
            n += 1
            max_t = max(max_t, os.path.getmtime(os.path.join(root, f)))
    return max_t


def cleanup_expired_git_repos() -> dict:
    """Remove local clones older than GIT_LOCAL_REPOS_TTL_DAYS (no-op if TTL <= 0)."""
    if GIT_LOCAL_REPOS_TTL_DAYS <= 0:
        return {'skipped': True, 'reason': 'GIT_LOCAL_REPOS_TTL_DAYS disabled'}
    base = Path(GIT_WORKDIR)
    if not base.exists():
        return {'removed': 0, 'names': []}
    ttl_sec = GIT_LOCAL_REPOS_TTL_DAYS * 86400
    now = time.time()
    removed = []
    for p in sorted(base.iterdir()):
        if not p.is_dir() or not (p / '.git').exists():
            continue
        if now - _repo_last_activity_ts(p) <= ttl_sec:
            continue
        shutil.rmtree(p)
        removed.append(p.name)
    if removed:
        log.info('git repo TTL: removed %d stale repo(s): %s', len(removed), removed)
    return {'removed': len(removed), 'names': removed, 'ttl_days': GIT_LOCAL_REPOS_TTL_DAYS}
