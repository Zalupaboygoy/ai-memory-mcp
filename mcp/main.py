#!/usr/bin/env python3
"""
AI Memory MCP Service v3 — Hybrid PostgreSQL + Neo4j
PostgreSQL for structured data, full-text search, embeddings.
Neo4j for graph relations, traversal, pattern matching.
"""
import os
import threading
import time

from starlette.middleware import Middleware

import config  # noqa: F401 — load .env before other app modules
from auth_middleware import AuthMiddlewareASGI
from mcp_app import mcp
from neo4j_ops import init_neo4j_schema

# Register tools (side-effect: @mcp.tool() on import)
import tools.gitea_tools  # noqa: F401
import tools.git_tools  # noqa: F401
import tools.graph  # noqa: F401
import tools.knowledge  # noqa: F401
import tools.semantic  # noqa: F401


def _git_ttl_background():
    from git_helpers import cleanup_expired_git_repos

    while True:
        time.sleep(86400)
        try:
            cleanup_expired_git_repos()
        except Exception:
            config.log.exception('git TTL cleanup failed')


if __name__ == '__main__':
    import uvicorn

    from git_helpers import cleanup_expired_git_repos

    cleanup_expired_git_repos()
    threading.Thread(target=_git_ttl_background, daemon=True, name='git-ttl').start()

    host = os.getenv('MCP_HOST', '0.0.0.0')
    port = int(os.getenv('MCP_PORT', 8000))
    init_neo4j_schema()
    app = mcp.http_app(
        transport='sse',
        middleware=[Middleware(AuthMiddlewareASGI)]
    )
    uvicorn.run(app, host=host, port=port)
