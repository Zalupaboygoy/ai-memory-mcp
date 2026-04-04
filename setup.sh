#!/usr/bin/env bash
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()  { echo -e "${CYAN}[*]${NC} $*"; }
ok()    { echo -e "${GREEN}[+]${NC} $*"; }
warn()  { echo -e "${YELLOW}[!]${NC} $*"; }
die()   { echo -e "${RED}[x]${NC} $*"; exit 1; }

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

# ── Prerequisites ──────────────────────────────────────────────────────────────
info "Checking prerequisites..."
command -v docker >/dev/null 2>&1 || die "Docker not found. Install: curl -fsSL https://get.docker.com | sh"
docker compose version >/dev/null 2>&1 || die "Docker Compose plugin not found."
command -v python3 >/dev/null 2>&1 || die "python3 required"
ok "Docker OK"

gen() { python3 -c "import secrets; print(secrets.token_hex($1))"; }

# ── Step 1: Network ────────────────────────────────────────────────────────────
echo
echo -e "${GREEN}━━ Step 1 / 5 — Network ━━${NC}"
DETECTED_IP=$(curl -sf https://api.ipify.org || curl -sf https://ifconfig.me || hostname -I | awk '{print $1}')
echo
read -rp "$(echo -e "${CYAN}Server public IP${NC} [${DETECTED_IP}]: ")" INPUT_IP
SERVER_IP="${INPUT_IP:-$DETECTED_IP}"
ok "Using IP: $SERVER_IP"

# ── Step 2: Gitea admin + MCP primary user (same username) ───────────────────
echo
echo -e "${GREEN}━━ Step 2 / 5 — Gitea admin & MCP primary user ━━${NC}"
echo "One username for Gitea admin and for MCP (Postgres users.id=1). Default: user"
echo
read -rp "$(echo -e "${CYAN}Username${NC} [user]: ")" GITEA_ADMIN_USER
GITEA_ADMIN_USER="${GITEA_ADMIN_USER:-user}"
if [[ ! "${GITEA_ADMIN_USER}" =~ ^[a-zA-Z0-9._-]+$ ]]; then
    die "Username may only contain letters, digits, . _ -"
fi
[[ ${#GITEA_ADMIN_USER} -le 100 ]] || die "Username too long"
MCP_FIRST_USERNAME="${GITEA_ADMIN_USER}"

read -rp "$(echo -e "${CYAN}Email${NC} [admin@local]: ")" GITEA_ADMIN_EMAIL
GITEA_ADMIN_EMAIL="${GITEA_ADMIN_EMAIL:-admin@local}"
GITEA_ADMIN_PASS=$(gen 12)
ok "Account: ${GITEA_ADMIN_USER} (Gitea password: 24 chars, generated)"

# ── Step 3: Caddy IP allowlist ─────────────────────────────────────────────────
echo
echo -e "${GREEN}━━ Step 3 / 5 — Caddy (reverse proxy) ━━${NC}"
echo "Restrict access to gitea / admin by client IP (MCP is not filtered; use Bearer token)."
read -rp "$(echo -e "${CYAN}Enable IP allowlist${NC} [y/N]: ")" _wl
case "${_wl,,}" in
    y|yes) CADDY_WHITELIST_ENABLED=true
        read -rp "$(echo -e "${CYAN}Allowed CIDRs${NC} (space-separated, e.g. 203.0.113.0/24 10.0.0.0/8): ")" CADDY_WHITELIST_IPS
        [[ -n "${CADDY_WHITELIST_IPS// }" ]] || die "Allowlist enabled: set at least one CIDR"
        ;;
    *) CADDY_WHITELIST_ENABLED=false
        CADDY_WHITELIST_IPS=
        ;;
esac
ok "CADDY_WHITELIST_ENABLED=${CADDY_WHITELIST_ENABLED}"

# Neo4j + Gitea public URLs (derived from SERVER_IP; same as .env.example defaults)
NEO4J_USER=neo4j
GITEA_DOMAIN="gitea.${SERVER_IP}.nip.io"
GITEA_ROOT_URL="https://${GITEA_DOMAIN}/"

# ── Step 4: Auto-summarize (optional); if off, LLM/embeddings prompts are skipped ──
echo
echo -e "${GREEN}━━ Step 4 / 5 — Auto-summarize & LLM ━━${NC}"
echo "If disabled, defaults match .env.example (empty keys, models unchanged)."
read -rp "$(echo -e "${CYAN}Enable AUTO_SUMMARIZE${NC} [y/N]: ")" _as
case "${_as,,}" in
    y|yes)
        AUTO_SUMMARIZE=true
        read -rp "$(echo -e "${CYAN}AUTO_SUMMARIZE_TRIGGER${NC} (entries per category) [20]: ")" _ast
        AUTO_SUMMARIZE_TRIGGER="${_ast:-20}"
        [[ "${AUTO_SUMMARIZE_TRIGGER}" =~ ^[0-9]+$ ]] || die "AUTO_SUMMARIZE_TRIGGER must be a number"
        read -rp "$(echo -e "${CYAN}LLM_CHAT_URL${NC}: ")" LLM_CHAT_URL
        LLM_CHAT_URL="${LLM_CHAT_URL:-}"
        read -rsp "$(echo -e "${CYAN}LLM_CHAT_KEY${NC}: ")" LLM_CHAT_KEY
        echo
        LLM_CHAT_KEY="${LLM_CHAT_KEY:-}"
        read -rp "$(echo -e "${CYAN}LLM_CHAT_MODEL${NC} [gemini-2.5-flash]: ")" LLM_CHAT_MODEL
        LLM_CHAT_MODEL="${LLM_CHAT_MODEL:-gemini-2.5-flash}"
        read -rp "$(echo -e "${CYAN}EMBEDDINGS_URL${NC} [https://generativelanguage.googleapis.com/v1beta]: ")" EMBEDDINGS_URL
        EMBEDDINGS_URL="${EMBEDDINGS_URL:-https://generativelanguage.googleapis.com/v1beta}"
        read -rsp "$(echo -e "${CYAN}EMBEDDINGS_KEY${NC} (semantic search): ")" EMBEDDINGS_KEY
        echo
        EMBEDDINGS_KEY="${EMBEDDINGS_KEY:-}"
        read -rp "$(echo -e "${CYAN}EMBEDDINGS_MODEL${NC} [models/text-embedding-004]: ")" EMBEDDINGS_MODEL
        EMBEDDINGS_MODEL="${EMBEDDINGS_MODEL:-models/text-embedding-004}"
        ok "AUTO_SUMMARIZE=true"
        ;;
    *)
        AUTO_SUMMARIZE=false
        AUTO_SUMMARIZE_TRIGGER=20
        LLM_CHAT_URL=
        LLM_CHAT_KEY=
        LLM_CHAT_MODEL=gemini-2.5-flash
        EMBEDDINGS_URL=https://generativelanguage.googleapis.com/v1beta
        EMBEDDINGS_KEY=
        EMBEDDINGS_MODEL=models/text-embedding-004
        ok "AUTO_SUMMARIZE=false (LLM/embeddings left at .env.example defaults)"
        ;;
esac

# ── Step 5: Cryptographic secrets (automatic — passwords/tokens) ──────────────
echo
echo -e "${GREEN}━━ Step 5 / 5 — Generating DB & Gitea secrets ━━${NC}"
info "Generating cryptographic secrets..."

POSTGRES_PASSWORD=$(gen 24)
MCP_DB_PASSWORD=$(gen 24)
GITEA_DB_PASSWORD=$(gen 24)
GITEA_SECRET_KEY=$(gen 32)
GITEA_INTERNAL_TOKEN=$(gen 48)
NEO4J_PASSWORD=$(gen 24)
ok "Secrets generated"

# ── Write .env ─────────────────────────────────────────────────────────────────
info "Writing .env..."
cat > .env << EOF
# Generated by setup.sh on $(date -u +"%Y-%m-%d %H:%M UTC")

SERVER_IP=${SERVER_IP}

MCP_FIRST_USERNAME=${MCP_FIRST_USERNAME}

CADDY_WHITELIST_ENABLED=${CADDY_WHITELIST_ENABLED}
CADDY_WHITELIST_IPS=${CADDY_WHITELIST_IPS}

POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
MCP_DB_PASSWORD=${MCP_DB_PASSWORD}
GITEA_DB_PASSWORD=${GITEA_DB_PASSWORD}

NEO4J_USER=${NEO4J_USER}
NEO4J_PASSWORD=${NEO4J_PASSWORD}

GITEA_SECRET_KEY=${GITEA_SECRET_KEY}
GITEA_INTERNAL_TOKEN=${GITEA_INTERNAL_TOKEN}
GITEA_DOMAIN=${GITEA_DOMAIN}
GITEA_ROOT_URL=${GITEA_ROOT_URL}

GITEA_TOKEN=
LLM_CHAT_URL=${LLM_CHAT_URL}
LLM_CHAT_KEY=${LLM_CHAT_KEY}
LLM_CHAT_MODEL=${LLM_CHAT_MODEL}
EMBEDDINGS_URL=${EMBEDDINGS_URL}
EMBEDDINGS_KEY=${EMBEDDINGS_KEY}
EMBEDDINGS_MODEL=${EMBEDDINGS_MODEL}
AUTO_SUMMARIZE=${AUTO_SUMMARIZE}
AUTO_SUMMARIZE_TRIGGER=${AUTO_SUMMARIZE_TRIGGER}
EOF
ok ".env written"

# ── Start stack (without mcp — no GITEA_TOKEN yet) ────────────────────────────
info "Starting postgres, neo4j, gitea, admin, caddy..."
docker compose up -d --build postgres neo4j gitea admin caddy

info "Waiting for postgres to be healthy..."
for i in $(seq 1 30); do
    docker compose exec postgres pg_isready -U postgres >/dev/null 2>&1 && break
    sleep 2
done
ok "Postgres ready"

info "Waiting for Neo4j to be healthy..."
for i in $(seq 1 60); do
    docker compose exec neo4j cypher-shell -u "${NEO4J_USER}" -p "${NEO4J_PASSWORD}" "RETURN 1" >/dev/null 2>&1 && break
    sleep 3
done
ok "Neo4j ready"

info "Waiting for Gitea to be ready..."
for i in $(seq 1 60); do
    curl -sf "http://localhost:3000" >/dev/null 2>&1 && break ||
    docker compose exec gitea curl -sf http://localhost:3000 >/dev/null 2>&1 && break
    sleep 3
done
ok "Gitea ready"
sleep 5

# ── Create Gitea users ─────────────────────────────────────────────────────────
info "Creating Gitea admin user '${GITEA_ADMIN_USER}'..."
docker compose exec -T gitea gitea admin user create \
    --username "${GITEA_ADMIN_USER}" \
    --password "${GITEA_ADMIN_PASS}" \
    --email "${GITEA_ADMIN_EMAIL}" \
    --admin \
    --must-change-password=false 2>&1 || warn "User may already exist, continuing..."

info "Creating Gitea service user 'ai-agent'..."
AI_AGENT_PASS=$(gen 24)
docker compose exec -T gitea gitea admin user create \
    --username ai-agent \
    --password "${AI_AGENT_PASS}" \
    --email ai@memory.local \
    --must-change-password=false 2>&1 || warn "ai-agent may already exist, continuing..."

# ── Generate Gitea API token ───────────────────────────────────────────────────
info "Generating Gitea API token for ai-agent..."
GITEA_TOKEN=$(docker compose exec -T gitea gitea admin user generate-access-token \
    --username ai-agent \
    --token-name mcp-token \
    --raw \
    --scopes 'write:repository,write:issue,read:user,write:user' 2>&1 | grep -Eo '[a-f0-9]{40}' | head -1)

if [[ -z "$GITEA_TOKEN" ]]; then
    warn "Could not auto-extract token, check output above"
else
    ok "Gitea token generated"
    sed -i "s/^GITEA_TOKEN=.*/GITEA_TOKEN=${GITEA_TOKEN}/" .env
fi

# ── Start MCP ──────────────────────────────────────────────────────────────────
info "Starting MCP..."
docker compose up -d --build mcp
sleep 5

# ── Create first MCP bearer token ─────────────────────────────────────────────
info "Creating initial MCP bearer token for user '${MCP_FIRST_USERNAME}' (id=1)..."
MCP_TOKEN=$(python3 -c "import secrets; print(secrets.token_hex(32))")
MCP_TOKEN_HASH=$(python3 -c "import hashlib,sys; print(hashlib.sha256(sys.argv[1].encode()).hexdigest())" "$MCP_TOKEN")
docker compose exec -T postgres psql -U mcpuser -d ai_memory -c \
    "INSERT INTO tokens (user_id, token_hash, name) VALUES (1, '${MCP_TOKEN_HASH}', 'default') ON CONFLICT DO NOTHING;" >/dev/null
ok "MCP token created"

# ── Final status ───────────────────────────────────────────────────────────────
echo
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  Stack deployed successfully!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo
echo -e "  Gitea:    https://${GITEA_DOMAIN}/"
echo -e "  MCP:      https://mcp.${SERVER_IP}.nip.io"
echo -e "  Admin UI: https://admin.${SERVER_IP}.nip.io"
echo -e "  Neo4j:    bolt://neo4j:7687 (internal only)"
echo
echo -e "  Gitea admin:  ${GITEA_ADMIN_USER} / ${GITEA_ADMIN_PASS}"
echo -e "  MCP token:    ${MCP_TOKEN}"
echo -e "  Neo4j:        ${NEO4J_USER} / ${NEO4J_PASSWORD}"
echo
echo -e "${YELLOW}  Save these credentials — they won't be shown again!${NC}"
echo -e "${YELLOW}  Admin UI token — use the MCP token above to login.${NC}"
echo
docker compose ps
