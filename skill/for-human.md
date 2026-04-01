# AI Memory MCP (Neo4j) — Setup Guide

## What is this skill

AI Memory MCP is a hybrid PostgreSQL + Neo4j knowledge base for AI agents.
PostgreSQL: structured data, full-text search, embeddings.
Neo4j: graph traversal, path finding, pattern matching.

## MCP Connection

- Transport: SSE
- URL: `https://mcp.YOUR_SERVER_IP.nip.io/sse`
- Auth: `Authorization: Bearer <MCP bearer token>` — token shown once by `setup.sh` or issued in **Admin UI** (not the same as `GITEA_TOKEN` in `.env`)

## Skill Configuration

Edit `configuration.md`:

- `repo_visibility`: `private` \| `public` — align with `write_entry(..., repo_visibility=)` and `gitea_create_repo(..., private=)`.
- `repo_owner`: human Gitea username — pass as `gitea_add_collaborator(..., username=)` when the repo should be shared with that account.

## Category Structure

Dot-notation, parent must exist before child.
Create via: create_category(path, name, description, agent_hint)

## importance_score

0.9-1.0 = critical, 0.5 = default, 0.1-0.3 = temp

## Gitea

Web UI: `https://gitea.YOUR_SERVER_IP.nip.io`  
Git SSH (host): port **2222** (see `docker-compose.yml` / `GITEA__server__SSH_PORT`).

After `gitea_create_repo`, if humans need access to repos owned by **`ai-agent`**, add a collaborator with the real API shape:

`gitea_add_collaborator(owner, repo, username, permission="write")`

Example: `gitea_add_collaborator("ai-agent", "my-repo", "<repo_owner from configuration.md>", "write")`.

`gitea_create_or_update_file` requires **`sha`** when updating an existing file.

## Graph: PG vs Neo4j

**Writes (dual):** `link_entries`, `unlink_entries` — Postgres `relations` + Neo4j edges (Neo4j errors are logged; PG commit still succeeds).

**Reads (Neo4j first, PG fallback):** `get_related`, `get_graph`.

**Neo4j-only analytics:** `find_paths`, `find_pattern`, `suggest_related`, `graph_stats`.

`find_paths(from_entry_id, to_entry_id, max_depth=5)` — `max_depth` is capped at **8** in code.

`find_pattern(description, limit=20)` — heuristic string matching; useful examples:

- `"orphan entries"` / `"isolated"` — entries with no entry-to-entry edges (beyond taxonomy)
- `"most connected"` / `"hub"` — high-degree entry nodes
- `"connected to entry 42"` / `"# 42"` — neighbors of entry id 42
- substring match for a relation preset, e.g. `"depends_on"`, `"deployed_on"` — lists edges of that type

Other phrases fall back to a text+graph search over titles/descriptions.

## semantic_search

Requires EMBEDDINGS_KEY in MCP server environment.
