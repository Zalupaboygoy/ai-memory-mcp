"""Neo4j driver, schema, and sync helpers for entries/categories."""
import json

from neo4j import GraphDatabase

from config import NEO4J_PASSWORD, NEO4J_URI, NEO4J_USER, log

_neo4j_driver = None


def get_neo4j():
    global _neo4j_driver
    if _neo4j_driver is None:
        _neo4j_driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    return _neo4j_driver


def neo4j_write(query, **params):
    driver = get_neo4j()
    with driver.session() as session:
        result = session.run(query, **params)
        return [dict(r) for r in result]


def neo4j_read(query, **params):
    driver = get_neo4j()
    with driver.session() as session:
        result = session.run(query, **params)
        return [dict(r) for r in result]


def init_neo4j_schema():
    try:
        driver = get_neo4j()
        with driver.session() as session:
            session.run("CREATE CONSTRAINT entry_uid IF NOT EXISTS FOR (e:Entry) REQUIRE (e.entry_id, e.user_id) IS UNIQUE")
            session.run("CREATE CONSTRAINT category_uid IF NOT EXISTS FOR (c:Category) REQUIRE (c.path, c.user_id) IS UNIQUE")
            session.run("CREATE INDEX entry_user IF NOT EXISTS FOR (e:Entry) ON (e.user_id)")
            session.run("CREATE INDEX category_user IF NOT EXISTS FOR (c:Category) ON (c.user_id)")
        log.info("Neo4j schema initialized")
    except Exception as e:
        log.error(f"Neo4j schema init failed: {e}")


def _sync_entry_to_neo4j(uid, entry_id, title, keywords, description, category_path, importance_score=0.5, metadata=None):
    try:
        neo4j_write(
            """
            MERGE (e:Entry {entry_id: $entry_id, user_id: $uid})
            SET e.title = $title,
                e.keywords = $keywords,
                e.description = $description,
                e.category_path = $category_path,
                e.importance_score = $importance_score,
                e.metadata = $metadata
            WITH e
            MERGE (c:Category {path: $category_path, user_id: $uid})
            MERGE (e)-[:BELONGS_TO]->(c)
            """,
            uid=uid, entry_id=entry_id, title=title, keywords=keywords or [],
            description=description or '', category_path=category_path,
            importance_score=importance_score, metadata=json.dumps(metadata or {})
        )
    except Exception as e:
        log.error(f"Neo4j sync entry failed: {e}")


def _delete_entry_from_neo4j(uid, entry_id):
    try:
        neo4j_write(
            "MATCH (e:Entry {entry_id: $entry_id, user_id: $uid}) DETACH DELETE e",
            uid=uid, entry_id=entry_id
        )
    except Exception as e:
        log.error(f"Neo4j delete entry failed: {e}")


def _sync_category_to_neo4j(uid, path, name, description=None):
    try:
        neo4j_write(
            """
            MERGE (c:Category {path: $path, user_id: $uid})
            SET c.name = $name, c.description = $description
            """,
            uid=uid, path=path, name=name, description=description or ''
        )
        parts = path.split('.')
        if len(parts) > 1:
            parent_path = '.'.join(parts[:-1])
            neo4j_write(
                """
                MATCH (c:Category {path: $path, user_id: $uid})
                MATCH (p:Category {path: $parent_path, user_id: $uid})
                MERGE (c)-[:CHILD_OF]->(p)
                """,
                uid=uid, path=path, parent_path=parent_path
            )
    except Exception as e:
        log.error(f"Neo4j sync category failed: {e}")


def _delete_category_from_neo4j(uid, path):
    try:
        neo4j_write(
            """
            MATCH (c:Category {user_id: $uid})
            WHERE c.path = $path OR c.path STARTS WITH $prefix
            DETACH DELETE c
            """,
            uid=uid, path=path, prefix=path + '.'
        )
    except Exception as e:
        log.error(f"Neo4j delete category failed: {e}")
