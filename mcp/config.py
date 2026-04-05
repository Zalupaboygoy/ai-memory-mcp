"""Environment and shared constants for the MCP service."""
import logging
import os

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

log = logging.getLogger('ai-memory')

DB_CONFIG = {
    'host': os.getenv('DB_HOST', '127.0.0.1'),
    'port': int(os.getenv('DB_PORT', 5432)),
    'dbname': os.getenv('DB_NAME', 'ai_memory'),
    'user': os.getenv('DB_USER', 'mcpuser'),
    'password': os.getenv('DB_PASSWORD', '')
}

NEO4J_URI = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
NEO4J_USER = os.getenv('NEO4J_USER', 'neo4j')
NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD', '')

GITEA_URL = os.getenv('GITEA_URL', 'http://gitea:3000')
GITEA_TOKEN = os.getenv('GITEA_TOKEN', '')
GITEA_AGENT_USER = os.getenv('GITEA_AGENT_USER', 'ai-agent')

LLM_CHAT_URL = os.getenv('LLM_CHAT_URL', '')
LLM_CHAT_KEY = os.getenv('LLM_CHAT_KEY', '')
LLM_CHAT_MODEL = os.getenv('LLM_CHAT_MODEL', 'gemini-2.5-flash')
EMBEDDINGS_URL = os.getenv('EMBEDDINGS_URL', 'https://generativelanguage.googleapis.com/v1beta')
EMBEDDINGS_KEY = os.getenv('EMBEDDINGS_KEY', '')
EMBEDDINGS_MODEL = os.getenv('EMBEDDINGS_MODEL', 'models/text-embedding-004')
AUTO_SUMMARIZE = os.getenv('AUTO_SUMMARIZE', 'false').lower() == 'true'
AUTO_SUMMARIZE_TRIGGER = int(os.getenv('AUTO_SUMMARIZE_TRIGGER', '20'))

GIT_WORKDIR = '/tmp/git-repos'
# Remove local clones older than N days (0 = disable automatic removal).
GIT_LOCAL_REPOS_TTL_DAYS = int(os.getenv('GIT_LOCAL_REPOS_TTL_DAYS', '7'))
GITEA_INTERNAL_URL = os.getenv('GITEA_URL', 'http://gitea:3000')
GITEA_AGENT_TOKEN = os.getenv('GITEA_TOKEN', '')
GITEA_AGENT_LOGIN = os.getenv('GITEA_AGENT_USER', 'ai-agent')

# Git identity for commits (and env fallback when ~/.gitconfig is missing in container).
GIT_COMMIT_USER_NAME = os.getenv('GIT_COMMIT_USER_NAME', 'ai-agent')
GIT_COMMIT_USER_EMAIL = os.getenv('GIT_COMMIT_USER_EMAIL', 'ai@memory.local')
