# Workflows

## Save Knowledge

```
search("topic")
get_structure()
write_entry(category_path, ...)
update_summary(category_path, "...")
link_entries(new_id, related_id, type)
```

## Explore Graph

```
graph_stats()
get_graph(entry_id, depth=2)
find_paths(a, b)
suggest_related(entry_id)
find_pattern("most connected")
```

## Code in Gitea

Typical service user is `ai-agent` (see `GITEA_AGENT_USER`). Replace `my-repo` and placeholders with real values from `configuration.md`.

```
gitea_create_repo(name, description, private=...)   # align with configuration.md repo_visibility
git_clone("ai-agent/my-repo", local_name)
git_write_file(local_name, filepath, content)
git_commit(local_name, "feat: ...")
git_push(local_name)
gitea_add_collaborator("ai-agent", "my-repo", "<repo_owner from configuration.md>", "write")
write_entry(category_path, title, keywords, description,
            gitea_url=..., repo_visibility=..., repo_owner=...)
```
