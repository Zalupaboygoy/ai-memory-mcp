"""Local git subprocess helpers and authenticated clone URLs."""
import os
import subprocess
from pathlib import Path

from config import GITEA_AGENT_LOGIN, GITEA_AGENT_TOKEN, GITEA_INTERNAL_URL, GIT_WORKDIR


def _git(repo_path: str, args: list, input_text: str = None) -> dict:
    path = Path(repo_path)
    if not path.exists():
        return {'error': f'Path does not exist: {repo_path}'}
    env = os.environ.copy()
    env['GIT_TERMINAL_PROMPT'] = '0'
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
