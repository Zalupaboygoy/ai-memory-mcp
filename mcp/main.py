#!/usr/bin/env python3
"""
AI Memory MCP Service v3 — Hybrid PostgreSQL + Neo4j
PostgreSQL for structured data, full-text search, embeddings.
Neo4j for graph relations, traversal, pattern matching.
"""
import os

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


if __name__ == '__main__':
    import uvicorn

    host = os.getenv('MCP_HOST', '0.0.0.0')
    port = int(os.getenv('MCP_PORT', 8000))
    init_neo4j_schema()
    app = mcp.http_app(
        transport='sse',
        middleware=[Middleware(AuthMiddlewareASGI)]
    )
    uvicorn.run(app, host=host, port=port)
