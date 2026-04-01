# Rules

- Always search before writing
- Call `update_summary` after material `write_entry` / category changes (recommended; tool tip says the same)
- Run `session-start.md` before substantial work
- Align `gitea_create_repo(..., private=)` and `write_entry(..., repo_visibility=)` with `configuration.md`
- After `gitea_create_repo` under `ai-agent`, add the human from `configuration.md` (`repo_owner`) via `gitea_add_collaborator` **only if** that user should have repo access
- For code-related entries, set `gitea_url`, `repo_visibility`, and `repo_owner` on `write_entry` when documenting a repo
- `importance_score`: 0.9-1.0 = critical, 0.5 = default, 0.1-0.3 = temp
- `link_entries` writes to both PG and Neo4j
- `get_graph` / `get_related` use Neo4j primary, fallback to PG
- Category paths dot-notation — parent before child
