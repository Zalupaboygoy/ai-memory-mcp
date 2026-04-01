#!/bin/bash
set -e

psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" <<-EOSQL
    CREATE USER mcpuser WITH PASSWORD '${MCP_DB_PASSWORD}';
    CREATE USER gitea WITH PASSWORD '${GITEA_DB_PASSWORD}';
    CREATE DATABASE ai_memory OWNER mcpuser;
    CREATE DATABASE gitea OWNER gitea;
    GRANT ALL PRIVILEGES ON DATABASE ai_memory TO mcpuser;
    GRANT ALL PRIVILEGES ON DATABASE gitea TO gitea;
EOSQL

psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d ai_memory <<-EOSQL
    CREATE EXTENSION IF NOT EXISTS vector;
    CREATE EXTENSION IF NOT EXISTS pg_trgm;

    CREATE OR REPLACE FUNCTION update_updated_at()
    RETURNS TRIGGER LANGUAGE plpgsql AS \$\$
    BEGIN
        NEW.updated_at = NOW();
        RETURN NEW;
    END;
    \$\$;

    CREATE TABLE users (
        id         SERIAL PRIMARY KEY,
        username   VARCHAR(100) UNIQUE NOT NULL,
        is_admin   BOOLEAN NOT NULL DEFAULT FALSE,
        created_at TIMESTAMP NOT NULL DEFAULT NOW()
    );

    CREATE TABLE tokens (
        id         SERIAL PRIMARY KEY,
        user_id    INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        token_hash VARCHAR(64) NOT NULL UNIQUE,
        name       VARCHAR(100) NOT NULL,
        created_at TIMESTAMP NOT NULL DEFAULT NOW(),
        expires_at TIMESTAMP
    );

    CREATE TABLE categories (
        id                 SERIAL PRIMARY KEY,
        user_id            INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        parent_id          INT REFERENCES categories(id) ON DELETE CASCADE,
        path               TEXT NOT NULL UNIQUE,
        name               TEXT NOT NULL,
        description        TEXT,
        agent_hint         TEXT,
        level              INT NOT NULL DEFAULT 0,
        summary            TEXT,
        summary_updated_at TIMESTAMP,
        created_at         TIMESTAMPTZ DEFAULT NOW(),
        updated_at         TIMESTAMPTZ DEFAULT NOW()
    );

    CREATE TABLE entries (
        id               SERIAL PRIMARY KEY,
        user_id          INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        category_id      INT NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
        title            TEXT NOT NULL,
        keywords         TEXT[] NOT NULL DEFAULT '{}',
        description      TEXT,
        content          TEXT,
        gitea_url        TEXT,
        repo_visibility  TEXT CHECK (repo_visibility IN ('public', 'private')),
        repo_owner       TEXT,
        importance_score DOUBLE PRECISION DEFAULT 0.5,
        metadata         JSONB DEFAULT '{}',
        embedding        vector(768),
        created_at       TIMESTAMPTZ DEFAULT NOW(),
        updated_at       TIMESTAMPTZ DEFAULT NOW()
    );

    CREATE TABLE summaries (
        id            SERIAL PRIMARY KEY,
        user_id       INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        scope_type    VARCHAR(20) NOT NULL CHECK (scope_type IN ('category', 'global')),
        scope_id      INT REFERENCES categories(id) ON DELETE CASCADE,
        level         INT NOT NULL DEFAULT 1,
        content       TEXT NOT NULL,
        entries_count INT DEFAULT 0,
        generated_by  VARCHAR(20) NOT NULL DEFAULT 'agent' CHECK (generated_by IN ('agent', 'auto')),
        created_at    TIMESTAMP NOT NULL DEFAULT NOW(),
        updated_at    TIMESTAMP NOT NULL DEFAULT NOW()
    );

    CREATE TABLE relations (
        id            SERIAL PRIMARY KEY,
        user_id       INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        from_entry_id INT NOT NULL REFERENCES entries(id) ON DELETE CASCADE,
        to_entry_id   INT NOT NULL REFERENCES entries(id) ON DELETE CASCADE,
        relation_type VARCHAR(50) NOT NULL,
        description   TEXT,
        created_at    TIMESTAMP NOT NULL DEFAULT NOW(),
        UNIQUE(from_entry_id, to_entry_id, relation_type)
    );

    CREATE UNIQUE INDEX idx_summaries_unique   ON summaries(user_id, scope_type, COALESCE(scope_id, 0));
    CREATE INDEX idx_categories_parent        ON categories(parent_id);
    CREATE INDEX idx_categories_path          ON categories(path);
    CREATE INDEX idx_categories_path_trgm     ON categories USING GIN (path gin_trgm_ops);
    CREATE INDEX idx_categories_user_id       ON categories(user_id);
    CREATE INDEX idx_entries_user_id          ON entries(user_id);
    CREATE INDEX idx_entries_category         ON entries(category_id);
    CREATE INDEX idx_entries_keywords         ON entries USING GIN (keywords);
    CREATE INDEX idx_entries_fts              ON entries USING GIN (to_tsvector('english', COALESCE(title,'') || ' ' || COALESCE(description,'') || ' ' || COALESCE(content,'')));
    CREATE INDEX idx_entries_gitea            ON entries(gitea_url) WHERE gitea_url IS NOT NULL;
    CREATE INDEX idx_tokens_hash              ON tokens(token_hash);
    CREATE INDEX idx_relations_from           ON relations(from_entry_id);
    CREATE INDEX idx_relations_to             ON relations(to_entry_id);
    CREATE INDEX idx_relations_user           ON relations(user_id);
    CREATE INDEX idx_summaries_user           ON summaries(user_id);

    CREATE TRIGGER categories_updated_at BEFORE UPDATE ON categories
        FOR EACH ROW EXECUTE FUNCTION update_updated_at();
    CREATE TRIGGER entries_updated_at BEFORE UPDATE ON entries
        FOR EACH ROW EXECUTE FUNCTION update_updated_at();

    GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO mcpuser;
    GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO mcpuser;

    INSERT INTO users (id, username, is_admin) VALUES (1, '${MCP_FIRST_USERNAME}', TRUE);
EOSQL
