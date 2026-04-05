# AI Memory MCP — API Reference

Base SSE URL: `https://mcp.YOUR_IP.nip.io/sse`
Protocol: MCP over SSE. Bearer token required.

Total tools: **64** (see [README.md](README.md) for the full list by group).

---

## Knowledge Base

### `get_structure`
Returns the full category tree. **Always call first.**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| depth | int | 2 | 1=root, 2=+children, 3=full |

```json
{"total_entries": 7, "total_categories": 12, "categories": [{"path": "tech", "agent_hint": "...", "subcategories": [...]}]}
```

---

### `get_subcategories`
| Param | Type | Description |
|-------|------|-------------|
| category_path | str | E.g. `"tech.programming"` |

---

### `search`
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| query | str | — | Full-text search |
| category_path | str | null | Filter by category |
| keywords | list[str] | null | AND-match keywords |
| limit | int | 10 | Max 50 |

> `content` is NOT returned — use `get_entry(id)` to fetch it.

---

### `write_entry`
| Param | Type | Req | Description |
|-------|------|-----|-------------|
| category_path | str | ✓ | Must exist. E.g. `"tech.programming.mycode"` |
| title | str | ✓ | Short title |
| keywords | list[str] | ✓ | For fast retrieval |
| description | str | ✓ | Detailed description |
| content | str | | Full content (code, text) |
| gitea_url | str | | URL to repo |
| repo_visibility | str | | `"public"` or `"private"` |
| repo_owner | str | | Gitea username |
| importance_score | float | | 0.0–1.0, default 0.5 |
| metadata | dict | | Any extra JSON |

When **`AUTO_SUMMARIZE=true`** (env) and the category’s entry count hits a multiple of **`AUTO_SUMMARIZE_TRIGGER`**, the response includes **`auto_summary_triggered`**. The server then calls the configured chat API (**`LLM_CHAT_URL`**, **`LLM_CHAT_KEY`**, **`LLM_CHAT_MODEL`**) to generate text and persists it via **`update_summary`** for that category. **`auto_summary`** in the response reports `{applied, reason, ...}`. If the LLM is not configured, **`reason`** is typically `llm_empty` and the category summary is unchanged.

---

### `get_entry`
| Param | Type | Description |
|-------|------|-------------|
| entry_id | int | Returns full entry including `content` |

---

### `update_entry`
| Param | Type | Description |
|-------|------|-------------|
| entry_id | int | Entry to update |
| (all other write_entry fields) | | Optional — only provided fields are updated |

---

### `delete_entry`
| Param | Type | Description |
|-------|------|-------------|
| entry_id | int | Entry ID to delete |

---

### `create_category`
| Param | Type | Description |
|-------|------|-------------|
| path | str | Dot-notation, parent must exist |
| name | str | Human-readable name |
| description | str | What this stores |
| agent_hint | str | When to use this category |

---

### `delete_category`
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| path | str | — | Category path |
| force | bool | false | Delete even if has entries/subcategories |

---

### `whoami`
No parameters. Returns current MCP user (`username`, `user_id`, `is_admin`).

---

### `semantic_search`
Vector similarity over `entries.embedding` (pgvector). Requires **`EMBEDDINGS_KEY`** in server `.env`; otherwise returns `error`.
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| query | str | — | Natural language query |
| category_path | str | null | Limit to category subtree |
| limit | int | 10 | Max results |

---

### `update_summary` / `update_global_summary`
| Tool | Params | Description |
|------|--------|-------------|
| `update_summary` | `category_path`, `summary_text` | Category-level summary text |
| `update_global_summary` | `summary_text` | Global summary |

---

### `get_context` / `get_global_context`
| Tool | Params | Description |
|------|--------|-------------|
| `get_context` | `category_path`, `include_children` (default true) | Category + summaries + entry counts |
| `get_global_context` | — | All top-level categories and global summary |

---

## Knowledge graph

Dual-write: PostgreSQL `relations` + Neo4j edges where available.

### `link_entries` / `unlink_entries`
| Tool | Key params | Description |
|------|------------|-------------|
| `link_entries` | `from_id`, `to_id`, `relation_type`, `description?` | Create relation |
| `unlink_entries` | `from_id`, `to_id`, `relation_type?` | Remove relation |

### `get_related`
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| entry_id | int | — | |
| relation_type | str | null | Filter |
| direction | str | `"both"` | `"incoming"`, `"outgoing"`, `"both"` |

### `get_graph`
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| entry_id | int | — | Start node |
| depth | int | 2 | Traversal depth |

### `find_paths`
| Param | Type | Description |
|-------|------|-------------|
| from_id | int | Start entry |
| to_id | int | End entry |
| max_depth | int | Upper bound on path length |

### `find_pattern`
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| description | str | — | Pattern name / query (see tool implementation) |
| limit | int | 20 | |

### `suggest_related`
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| entry_id | int | — | |
| limit | int | 10 | Suggestions by graph proximity |

### `graph_stats`
No parameters. Aggregate Neo4j statistics (counts, orphans, relation mix).

---

## Gitea — Repository Management

### `gitea_create_repo`
Create repo under the MCP Gitea service user (see `GITEA_AGENT_USER` in deployment; default `ai-agent`).
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| name | str | — | Repo name (no spaces) |
| description | str | `""` | Short description |
| private | bool | true | Visibility |
| auto_init | bool | true | Initialize with README |
| default_branch | str | `"main"` | Default branch |

Returns: `{full_name, html_url, clone_url, ssh_url, private}`

---

### `gitea_list_repos`
List repos accessible to the MCP Gitea service user.
| Param | Type | Default |
|-------|------|---------|
| limit | int | 20 |

---

### `gitea_get_repo_info`
| Param | Type | Description |
|-------|------|-------------|
| owner | str | Repo owner |
| repo | str | Repo name |

---

### `gitea_update_repo`
Change repo settings.
| Param | Type | Description |
|-------|------|-------------|
| owner | str | |
| repo | str | |
| description | str | New description |
| private | bool | Change visibility |
| website | str | Repo website URL |
| default_branch | str | Change default branch |

---

### `gitea_delete_repo`
**PERMANENT.** Cannot be undone.
| Param | Type |
|-------|------|
| owner | str |
| repo | str |

---

### `gitea_transfer_repo`
Transfer ownership to another user.
| Param | Type | Description |
|-------|------|-------------|
| owner | str | Current owner |
| repo | str | |
| new_owner | str | Target username |

---

### `gitea_fork_repo`
Fork into `ai-agent` account.
| Param | Type | Description |
|-------|------|-------------|
| owner | str | Source owner |
| repo | str | Source repo |
| fork_name | str | Optional new name |

---

### `gitea_search_repos`
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| query | str | — | Search string |
| limit | int | 10 | |

---

## Gitea — Branches

### `gitea_list_branches`
| Param | Type |
|-------|------|
| owner | str |
| repo | str |

Returns: `{count, branches: [{name, sha}]}`

---

### `gitea_create_branch`
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| owner | str | — | |
| repo | str | — | |
| branch_name | str | — | New branch name |
| from_branch | str | `"main"` | Source branch |

---

### `gitea_delete_branch`
| Param | Type |
|-------|------|
| owner | str |
| repo | str |
| branch_name | str |

---

## Gitea — Files

### `gitea_list_files`
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| owner | str | — | |
| repo | str | — | |
| path | str | `""` | Directory path (empty = root) |
| ref | str | `"main"` | Branch or commit |

---

### `gitea_get_file`
Get decoded file content + sha (needed for update).
| Param | Type | Default |
|-------|------|---------|
| owner | str | — |
| repo | str | — |
| filepath | str | — |
| ref | str | `"main"` |

Returns: `{path, name, size, sha, content, html_url}`

---

### `gitea_create_or_update_file`
Create or update a file. **Provide `sha` when updating.**
| Param | Type | Req | Description |
|-------|------|-----|-------------|
| owner | str | ✓ | |
| repo | str | ✓ | |
| filepath | str | ✓ | E.g. `"src/main.py"` |
| content | str | ✓ | Plain text content |
| message | str | ✓ | Commit message |
| branch | str | | Default: `"main"` |
| sha | str | | Required when updating existing file |

---

### `gitea_delete_file`
| Param | Type | Req | Description |
|-------|------|-----|-------------|
| owner | str | ✓ | |
| repo | str | ✓ | |
| filepath | str | ✓ | |
| message | str | ✓ | Commit message |
| sha | str | ✓ | Current file sha |
| branch | str | | Default: `"main"` |

---

## Gitea — Commits

### `gitea_get_commits`
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| owner | str | — | |
| repo | str | — | |
| branch | str | `"main"` | |
| limit | int | 10 | |

Returns: `{branch, count, commits: [{sha, author, date, message}]}`

---

## Gitea — Collaborators

### `gitea_list_collaborators`
| Param | Type |
|-------|------|
| owner | str |
| repo | str |

---

### `gitea_add_collaborator`
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| owner | str | — | |
| repo | str | — | |
| username | str | — | |
| permission | str | `"write"` | `"read"`, `"write"`, or `"admin"` |

---

### `gitea_remove_collaborator`
| Param | Type |
|-------|------|
| owner | str |
| repo | str |
| username | str |

---

## Gitea — Issues

### `gitea_create_issue`
| Param | Type | Description |
|-------|------|-------------|
| owner | str | |
| repo | str | |
| title | str | Issue title |
| body | str | Body (markdown) |

---

### `gitea_list_issues`
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| owner | str | — | |
| repo | str | — | |
| state | str | `"open"` | `"open"`, `"closed"`, or `"all"` |
| limit | int | 20 | |

---

### `gitea_close_issue`
| Param | Type | Description |
|-------|------|-------------|
| owner | str | |
| repo | str | |
| issue_number | int | |
| comment | str | Optional comment before closing |

---

## Local Git Operations

All local repos live in `/tmp/git-repos/<local_name>/` inside the MCP container.
Commits are made as `ai-agent <ai@memory.local>` automatically.

> **Note:** `/tmp` is ephemeral — data is lost on container restart. Use push to persist.

> **TTL:** By default, a local clone is **removed after 7 days** without activity (based on mtime under `.git`). A background job runs daily; cleanup also runs once at MCP startup. Set env `GIT_LOCAL_REPOS_TTL_DAYS=0` to disable automatic deletion.

---

### `git_clone`
Clone a Gitea repo locally. Credentials injected automatically.
| Param | Type | Description |
|-------|------|-------------|
| repo_full_name | str | `"owner/repo"` e.g. `"YOUR_OWNER/your-repo"` |
| local_name | str | Local folder name (default: repo name) |
| branch | str | Branch to clone (default: default branch) |

Returns: `{success, local_path, repo, recent_commits}`

---

### `git_init`
Init new empty local repo, optionally link to Gitea remote.
| Param | Type | Description |
|-------|------|-------------|
| local_name | str | Folder name |
| repo_full_name | str | Optional: `"owner/repo"` for remote |

---

### `git_status`
| Param | Type |
|-------|------|
| local_name | str |

Returns: `{branch, staged, unstaged, untracked, clean}`

---

### `git_write_file`
Write (create or overwrite) a file in local repo.
| Param | Type | Description |
|-------|------|-------------|
| local_name | str | |
| filepath | str | Relative path, e.g. `"src/main.py"` |
| content | str | File content |

---

### `git_read_file`
| Param | Type | Description |
|-------|------|-------------|
| local_name | str | |
| filepath | str | Relative path |

Returns: `{filepath, size, content}`

---

### `git_delete_file`
Delete file from disk (not committed yet).
| Param | Type |
|-------|------|
| local_name | str |
| filepath | str |

---

### `git_list_local_files`
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| local_name | str | — | |
| subpath | str | `""` | Subdirectory (empty = root) |

Returns: `{items: [{name, type, size}]}`

---

### `git_add`
Stage files.
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| local_name | str | — | |
| paths | list[str] | null | Files to stage. null = all (`git add -A`) |

---

### `git_commit`
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| local_name | str | — | |
| message | str | — | Commit message |
| add_all | bool | true | Auto-stage all before commit |

Returns: `{commit_sha, message, output}`

---

### `git_push`
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| local_name | str | — | |
| branch | str | current | Branch to push |
| force | bool | false | Force push |

---

### `git_pull`
| Param | Type | Default |
|-------|------|---------|
| local_name | str | — |
| branch | str | current |

---

### `git_log`
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| local_name | str | — | |
| limit | int | 10 | |
| branch | str | current | |

Returns: `{commits: [{sha, author, email, date, message}]}`

---

### `git_diff`
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| local_name | str | — | |
| filepath | str | null | Specific file (null = all) |
| staged | bool | false | Show staged diff |

---

### `git_branch`
List, create, or delete local branches.
| Param | Type | Description |
|-------|------|-------------|
| local_name | str | |
| create | str | Branch name to create |
| delete | str | Branch name to delete |

With no create/delete: returns `{current, branches}`

---

### `git_checkout`
| Param | Type |
|-------|------|
| local_name | str |
| branch | str |

---

### `git_list_repos`
List all cloned repos in `/tmp/git-repos/`.
No params. Returns: `{count, workdir, repos: [{name, path, branch, last_commit}]}`

---

### `git_remove_local`
Delete local clone. Does NOT delete remote Gitea repo.
| Param | Type |
|-------|------|
| local_name | str |

---

## Error Responses

All tools return on failure:
```json
{"error": "Description"}
```

## Connection Info

```
SSE:      https://mcp.YOUR_IP.nip.io/sse
Messages: https://mcp.YOUR_IP.nip.io/messages/
Auth:     Authorization: Bearer <token>
```
