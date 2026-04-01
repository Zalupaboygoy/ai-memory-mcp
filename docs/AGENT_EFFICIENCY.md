AGENT EFFICIENCY - AI Memory MCP

WHEN TO READ FILES:
- Only if: new session with no context, OR someone else changed the file
- Use git_diff first - if you wrote the file this session, diff shows external changes without full read
- Never re-read a file you already wrote/read this session

COPYING FILES/REPOS (zero token cost):
- git_copy_file(src_repo, src_path, dest_repo, dest_path) - single file
- git_clone_to(src_repo, dest_repo, new_remote?) - entire repo
- Never read+write files to copy - costs 2x file size in tokens

OPERATION COSTS:
- git_write_file / git_read_file large files = high token cost
- git_diff small change = relatively cheap vs full file read
- git_copy_file / git_clone_to = low metadata cost vs read+write

GENERAL:
- Batch independent MCP tool calls in parallel when the host allows
- Gitea API base inside the stack: `http://gitea:3000` (from MCP container)
- Local repos in /tmp/git-repos/ - ephemeral, always push after commit
- Review session summaries critically - don't auto-execute stale plans
