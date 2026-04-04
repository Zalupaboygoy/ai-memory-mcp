# AI Memory MCP — Setup Guide

Deploy the full stack with a single command.

## Prerequisites

- Ubuntu 24.04 LTS (or any Linux with Docker)
- Root access
- Open ports: `80`, `443` (HTTPS: Gitea / MCP / Admin), `2222` (Git по SSH с ключом). Базы на хост не проброшены
- Public IP

---

## Install Docker (if not installed)

```bash
curl -fsSL https://get.docker.com | sh
systemctl enable --now docker
```

---

## Deploy

```bash
git clone https://gitea.YOUR_IP.nip.io/YOUR_OWNER/YOUR_REPO.git /opt/docker-stack
cd /opt/docker-stack
./setup.sh
```

Substitute your `YOUR_IP`, Gitea owner, and repository name (`YOUR_OWNER` / `YOUR_REPO`).

The script will ask for (5 steps):
- **Step 1:** server public IP (auto-detected)
- **Step 2:** Gitea admin username and email (password for Gitea admin is **generated**, 24 hex chars)
- **Step 3:** optional Caddy IP allowlist for **Gitea + Admin** (`CADDY_WHITELIST_*`; MCP is not IP-restricted)
- **Step 4:** optional `AUTO_SUMMARIZE` and LLM/embeddings (if disabled, defaults match `.env.example`; no prompts)
- **Step 5:** no questions — generates DB/Gitea/Neo4j secrets and writes `.env`

`NEO4J_USER`, `GITEA_DOMAIN`, `GITEA_ROOT_URL` are derived from `SERVER_IP` (see `.env.example`).

Then everything runs automatically:
1. Writes `.env` and starts postgres, neo4j, gitea, admin, caddy — Caddy loads `caddy/Caddyfile` with `{$SERVER_IP}` and optional whitelist (Gitea/Admin only) from `.env`
2. Creates Gitea users (admin + service user `ai-agent`)
3. Generates Gitea API token for `ai-agent`, appends to `.env`
4. Starts MCP, creates the first MCP bearer token for `MCP_FIRST_USERNAME`
5. Prints URLs and credentials

At the end you will see:
```
  Gitea:    https://gitea.1.2.3.4.nip.io
  MCP:      https://mcp.1.2.3.4.nip.io
  Admin UI: https://admin.1.2.3.4.nip.io

  Gitea admin:  <username> / <password>
  MCP token:    <token>   ← save this, shown only once
```

---

## Connect MCP to an Agent

Claude Desktop / Cursor (`mcp_servers.json`):
```json
{
  "ai-memory": {
    "url": "https://mcp.YOUR_IP.nip.io/sse",
    "transport": "sse",
    "headers": {
      "Authorization": "Bearer YOUR_MCP_TOKEN"
    }
  }
}
```

---

## Token Management

Admin UI: `https://admin.YOUR_IP.nip.io`

Login with any **valid MCP bearer token** whose user has **`is_admin = TRUE`** (the first user created by `setup.sh` is admin).

---

## Useful Commands

```bash
cd /opt/docker-stack

docker compose ps
docker compose logs -f mcp
docker compose logs -f caddy
docker compose up -d --build mcp   # rebuild after code changes
docker compose restart gitea
docker compose down
docker compose down -v             # WARNING: deletes all data
```

---

## Backup

```bash
docker exec postgres pg_dump -U mcpuser ai_memory > backup_$(date +%Y%m%d).sql
docker exec postgres pg_dump -U gitea gitea > backup_gitea_$(date +%Y%m%d).sql
```

---

## Redeploy / Clean Install

```bash
docker compose down -v   # delete all data
rm .env
./setup.sh               # run again
```
