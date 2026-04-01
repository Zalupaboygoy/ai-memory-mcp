# Configuration

Edit values once per deployment; use them when calling `gitea_create_repo` (`private` vs `public`) and `write_entry` (`repo_visibility`, `repo_owner`).

```yaml
# "public" | "private" — must match write_entry.repo_visibility when documenting code entries
repo_visibility: private

# Gitea username (human) to grant access to repos created under the MCP service user (ai-agent)
repo_owner: YOUR_GITEA_USERNAME
```

`gitea_create_repo(..., private=True)` corresponds to `repo_visibility: private`.
