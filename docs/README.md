# AI Memory MCP — v3 (Hybrid PostgreSQL + Neo4j)

Hybrid knowledge base for AI agents. PostgreSQL for structured data, full-text search, embeddings. Neo4j for graph relations, traversal, pattern matching.

## Quick Start

```bash
git clone https://gitea.YOUR_IP.nip.io/YOUR_OWNER/YOUR_REPO.git /opt/docker-stack
cd /opt/docker-stack
./setup.sh
```

Replace `YOUR_IP` with your server’s public address, and `YOUR_OWNER` / `YOUR_REPO` with the Gitea user and repository name (fork or mirror of this project).

See [SETUP.md](SETUP.md) for details.

---

## Services

| Service | URL / access | Notes |
|---------|-----|-------|
| MCP | `https://mcp.YOUR_IP.nip.io/sse` | Bearer token; TLS via Caddy |
| Admin UI | `https://admin.YOUR_IP.nip.io` | Tokens and users (admin token) |
| Gitea | `https://gitea.YOUR_IP.nip.io` | Web UI; Git **SSH** on host port **2222** (see `docker-compose.yml`) |
| PostgreSQL | Docker network only | **Not** published on host; `pgvector` + `ai_memory` DB |
| Neo4j | Docker network only (`bolt://neo4j:7687` inside stack) | **Not** published on host |

## Architecture

```
Caddy (TLS, optional IP allowlist) -> MCP (FastMCP + SSE + auth middleware)
                                   -> Admin UI (FastAPI)
                                   -> Gitea :3000

MCP -> PostgreSQL 16 (pgvector)  [structured data, FTS, embeddings]
    -> Neo4j 5 (APOC)            [graph relations, traversal, patterns]
```

## Database Schema

### PostgreSQL (source of truth)
```
users        (id, username, is_admin, created_at)
tokens       (id, user_id, token_hash[sha256], name, created_at, expires_at)
categories   (id, user_id, parent_id, path, name, description, agent_hint, level, summary)
entries      (id, user_id, category_id, title, keywords[], description, content,
              gitea_url, repo_visibility, repo_owner, importance_score, metadata,
              embedding vector(768))
summaries    (id, user_id, scope_type, scope_id, level, content, entries_count,
              generated_by, created_at, updated_at)
relations    (id, user_id, from_entry_id, to_entry_id, relation_type,
              description, created_at)
```

### Neo4j (synced graph)
```
(:Entry {entry_id, user_id, title, keywords, description, category_path, importance_score})
(:Category {path, user_id, name, description})

(Entry)-[:BELONGS_TO]->(Category)
(Category)-[:CHILD_OF]->(Category)
(Entry)-[:RELATION_TYPE {description, relation_type, pg_id}]->(Entry)
```

## MCP Tools (64)

### User Info
- `whoami()`

### Memory (PostgreSQL)
- `get_structure(depth)`, `get_subcategories(path)`
- `search(query, category_path?, keywords?, limit)`, `semantic_search(query, category_path?, limit)` (needs `EMBEDDINGS_KEY`)
- `write_entry(...)`, `get_entry(id)`, `update_entry(id, ...)`, `delete_entry(id)`
- `create_category(path, name, description, agent_hint)`, `delete_category(path, force?)`

### Summaries (PostgreSQL)
- `update_summary(category_path, text)`, `update_global_summary(text)`
- `get_context(category_path, include_children?)`, `get_global_context()`

### Graph (Neo4j with PostgreSQL fallback)
- `link_entries(from_id, to_id, relation_type, description?)` — dual write PG + Neo4j
- `get_related(entry_id, relation_type?, direction?)` — Neo4j primary, PG fallback
- `get_graph(entry_id, depth)` — Neo4j traversal, PG fallback
- `unlink_entries(from_id, to_id, relation_type?)` — dual delete

### Graph (Neo4j analytics)
- `find_paths(from_id, to_id, max_depth)` — all shortest paths between entries
- `find_pattern(description, limit)` — pattern matching (orphans, hubs, relation types)
- `suggest_related(entry_id, limit)` — recommendations by graph proximity
- `graph_stats()` — node/edge counts, top connected, relation distribution, orphans

### Gitea (22 tools)
`gitea_create_repo`, `gitea_list_repos`, `gitea_get_repo_info`, `gitea_list_files`,
`gitea_get_file`, `gitea_create_or_update_file`, `gitea_delete_file`,
`gitea_create_issue`, `gitea_close_issue`, `gitea_search_repos`,
`gitea_transfer_repo`, `gitea_add_collaborator`, `gitea_remove_collaborator`,
`gitea_delete_repo`, `gitea_update_repo`, `gitea_fork_repo`,
`gitea_list_branches`, `gitea_create_branch`, `gitea_delete_branch`,
`gitea_get_commits`, `gitea_list_collaborators`, `gitea_list_issues`

### Local Git (19 tools)
`git_clone`, `git_init`, `git_status`, `git_write_file`, `git_read_file`,
`git_delete_file`, `git_copy_file`, `git_clone_to`, `git_list_local_files`,
`git_add`, `git_commit`, `git_push`, `git_pull`, `git_log`, `git_diff`,
`git_branch`, `git_checkout`, `git_list_repos`, `git_remove_local`

## Data Flow

```
write_entry() -> PostgreSQL INSERT -> Neo4j MERGE (Entry + BELONGS_TO)
link_entries() -> PostgreSQL INSERT -> Neo4j MERGE (relationship)
delete_entry() -> PostgreSQL DELETE -> Neo4j DETACH DELETE
get_graph() -> Neo4j traversal (fast) | PostgreSQL fallback (if Neo4j down)
```

## Security

- Secrets in `.env` (not committed; see `.gitignore` and `.env.example`)
- MCP tokens stored as SHA256 hashes; only hashes in Postgres
- Multi-tenant: each user sees only their own data
- TLS via Caddy (Let's Encrypt); optional **IP allowlist** (`CADDY_WHITELIST_*`)
- PostgreSQL and Neo4j have **no host port mappings**; `backend` network is `internal: true`
- Admin UI and MCP behind the same Caddy hostnames as in `caddy/Caddyfile`

## Requirements

- 8 GB RAM recommended (PG + Neo4j + Gitea + Caddy + MCP)
- Docker + Docker Compose

## Agent Workflow

```
1. get_global_context()       -> overview of user knowledge
2. get_context("tech")        -> category with summaries
3. search(query)              -> find entries (PG full-text)
4. get_entry(id)              -> full content
5. write_entry(...)           -> save (PG + Neo4j sync)
6. update_summary(path, text) -> update summary
7. link_entries(a, b, type)   -> link (PG + Neo4j)
8. get_graph(id, depth=3)     -> explore graph (Neo4j)
9. find_paths(a, b)           -> paths between entries (Neo4j)
10. suggest_related(id)       -> recommendations (Neo4j)
11. graph_stats()             -> graph overview (Neo4j)
```
