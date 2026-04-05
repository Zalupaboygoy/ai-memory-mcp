# Tools: Writing

Invocation shape (MCP `name` + `arguments`): see **`tool-invocation.md`**. Parameter names below are exact keys for `arguments`.

```
write_entry(category_path, title, keywords, description,
            content?, gitea_url?, repo_visibility?, repo_owner?,
            importance_score?, metadata?)
update_entry(entry_id, ...fields)
delete_entry(entry_id)
```
