# AI Agent Guide — AI Memory MCP

---

## Connecting

```
SSE URL: https://mcp.YOUR_IP.nip.io/sse
Auth:    Authorization: Bearer <token>
```

Total available tools: **64**

---

## Tool Groups

| Group | Tools | Purpose |
|-------|-------|---------|
| User + memory | 15 | `whoami`, categories, `search`, `semantic_search`, entries, summaries, `get_context` / `get_global_context` |
| Graph | 8 | `link_entries`, `get_related`, `get_graph`, `unlink_entries`, `find_paths`, `find_pattern`, `suggest_related`, `graph_stats` |
| Gitea | 22 | Repos, branches, files, commits, collaborators, issues (see [README.md](README.md)) |
| Local Git | 19 | Clone, edit, commit, push in `/tmp/git-repos/` |

---

## Workflow 1: Knowledge Base

```
1. get_global_context()     → overview of all user knowledge
2. get_context("tech")      → drill into category with summaries
3. search(query)            → find existing entries
4. get_entry(id)            → full content
5. write_entry(...)         → store new knowledge
6. update_summary(path, ..) → keep summaries current
7. link_entries(a, b, type) → record relationships
```

### Category Paths (dot-notation)
```
tech
tech.programming
tech.programming.mycode
tech.infrastructure
tech.tools
life
life.notes
```

### Writing code entries — always include gitea fields
```json
{
  "gitea_url": "https://gitea.YOUR_IP.nip.io/YOUR_OWNER/your-repo",
  "repo_visibility": "public",
  "repo_owner": "YOUR_OWNER"
}
```

Replace `YOUR_OWNER` and `your-repo` with your real Gitea owner and repository name.

### Search tips
1. Start with `get_global_context()` — check if category exists
2. Combine query + keywords: `query="auth"` + `keywords=["jwt", "python"]`
3. With **`EMBEDDINGS_KEY`** configured, use `semantic_search` for meaning-based retrieval
4. No results → broaden query, remove `category_path`, try parent
5. Too many → add `category_path`, add `keywords`, reduce `limit`

---

## Workflow 2: Working with existing repo

```
1. gitea_search_repos(query)                      → find the repo
2. git_clone("owner/repo")                        → clone to /tmp/git-repos/
3. git_list_local_files(local_name)               → see structure
4. git_read_file(local_name, path)                → read file
5. git_write_file(local_name, path, content)      → edit file
6. git_commit(local_name, "message")              → commit (auto-stages all)
7. git_push(local_name)                           → push to Gitea
8. git_remove_local(local_name)                   → cleanup /tmp
```

---

## Workflow 3: Creating a new project

Repos are created as the MCP Gitea service user (default `ai-agent`; see `GITEA_AGENT_USER`). Use the actual `owner/repo` from `gitea_create_repo` or the Gitea UI.

```
1. gitea_create_repo(name, description, private=False)
2. git_clone("YOUR_SERVICE_USER/your-repo")
3. git_write_file(...) × N
4. git_commit(local_name, "feat: initial commit")
5. git_push(local_name)
6. gitea_transfer_repo("YOUR_SERVICE_USER", "your-repo", "YOUR_OWNER")
7. write_entry(category_path="tech.programming.mycode", gitea_url=...)
```

---

## Knowledge Graph

```
link_entries(from_id=1, to_id=2, relation_type="depends_on")
get_related(entry_id=1)                    → adjacent nodes
get_graph(entry_id=1, depth=2)             → full subgraph
unlink_entries(from_id=1, to_id=2)         → remove edge
```

Common relation types: `depends_on`, `used_by`, `deployed_on`, `extends`, `documents`

---

## Summaries

Each category has a `summary` — a brief description of what it contains.
Update after every significant change:

```
update_summary("tech.programming", "Python/FastAPI projects...")
update_global_summary("User works on AI tools, backend services...")
```

`get_global_context()` → fast overview without loading all entries.
