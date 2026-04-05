# How tools are invoked (MCP)

All capabilities exposed by this server are **MCP tools**: one **name** (matches the Python function name, e.g. `write_entry`, `git_clone`) and a single JSON object of **arguments**.

## Transport and auth

- **Protocol:** MCP over **SSE** (HTTP). Clients connect to the SSE endpoint, then send JSON-RPC-style messages (including `tools/call`) on the HTTP channel your MCP client uses (often POST with `Content-Type: application/json`).
- **Auth:** Every HTTP request must include  
  `Authorization: Bearer <token>`  
  The token is issued by the deployment (see operator docs / `for-human.md`). Without it, the server returns **401**.

Authoritative URL pattern and stack notes: `docs/MCP_API.md` (top of file).

## JSON shape for `tools/call`

MCP clients should send a request whose `params` include:

| Field | Meaning |
|--------|---------|
| `name` | Tool name, **exact string**, snake_case — e.g. `write_entry`, `search`, `git_clone`. |
| `arguments` | **Object** of named parameters for that tool. Types match the tool definition (strings, numbers, arrays, objects). |

Example (illustrative):

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "write_entry",
    "arguments": {
      "category_path": "tech.infrastructure",
      "title": "Note",
      "keywords": ["infra"],
      "description": "Short summary",
      "content": "Optional body"
    }
  }
}
```

Some clients label the argument object **`args`** instead of **`arguments`**. This server normalizes that: if `params.args` is present and `params.arguments` is missing or empty, **`arguments` is filled from `args`** before the tool runs. Prefer **`arguments`** (MCP-standard) when the client supports it.

## Rules that prevent “empty” tool input

1. **Use the real parameter names** from the tool definition — not synonyms. Example: `write_entry` requires **`category_path`**, not `category`.
2. **Required fields** must all appear inside `arguments` (see per-tool tables in `docs/MCP_API.md` and the `tools-*.md` skill files).
3. **Types:** lists are JSON arrays (`["a","b"]`), booleans are `true`/`false`, optional fields may be omitted.

If the client sends the wrong key for `arguments`/`args` or wrong parameter names, the server may see **`arguments` as `{}`** and the tool will fail or no-op.

## Groups of tools (same invocation pattern)

| Group | Skill file | Notes |
|--------|------------|--------|
| Categories & KB CRUD, search | `tools-categories.md`, `tools-reading.md`, `tools-writing.md`, `tools-searching.md`, `tools-summaries.md` | User-scoped data; token resolves `user_id`. |
| PostgreSQL graph helpers | `tools-graph-pg.md` | Same as above. |
| Neo4j graph | `tools-graph-neo4j.md` | Same as above. |
| Gitea API | `tools-gitea.md` | Uses server-side Gitea token; still invoked like any MCP tool. |
| Local git | `tools-git.md` | Operates on paths under `/tmp/git-repos/` in the MCP container; `local_name` is the folder name. |

There is **no** separate REST surface for these operations from the agent’s perspective: **everything** goes through **`tools/call`** with `name` + `arguments`.

## Where to look up parameters

1. **`docs/MCP_API.md`** — full parameter tables and return shapes.
2. **`skill/tools-*.md`** — compact signatures and groupings.
3. **`workflows.md`** — suggested order of calls for common tasks.

## Session bootstrap (what to call first)

See **`session-start.md`** for the recommended initial tool sequence after connecting.
