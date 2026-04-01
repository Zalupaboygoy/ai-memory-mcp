"""Graph ops (Neo4j + PG fallback). Full contract: project skill."""
import json
from typing import Dict, List, Optional

import psycopg2.extras

from config import log
from db import get_conn
from mcp_app import mcp
from neo4j_ops import neo4j_read, neo4j_write
from user_context import _get_uid

@mcp.tool()
def link_entries(
    from_entry_id: int,
    to_entry_id: int,
    relation_type: str,
    description: Optional[str] = None
) -> Dict:
    """INSERT relation + Neo4j MERGE typed edge (dynamic rel type)."""
    uid = _get_uid()
    if from_entry_id == to_entry_id:
        return {'error': 'Cannot link an entry to itself'}
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT id, title FROM entries WHERE id = %s AND user_id = %s",
                (from_entry_id, uid)
            )
            from_entry = cur.fetchone()
            if not from_entry:
                return {'error': f'Entry {from_entry_id} not found'}
            cur.execute(
                "SELECT id, title FROM entries WHERE id = %s AND user_id = %s",
                (to_entry_id, uid)
            )
            to_entry = cur.fetchone()
            if not to_entry:
                return {'error': f'Entry {to_entry_id} not found'}

            cur.execute("""
                INSERT INTO relations (user_id, from_entry_id, to_entry_id, relation_type, description)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (from_entry_id, to_entry_id, relation_type) DO UPDATE
                    SET description = EXCLUDED.description
                RETURNING id
            """, (uid, from_entry_id, to_entry_id, relation_type, description))
            row = cur.fetchone()
            conn.commit()

        rel_type_upper = relation_type.upper()
        try:
            neo4j_write(
                f"""
                MATCH (a:Entry {{entry_id: $from_id, user_id: $uid}})
                MATCH (b:Entry {{entry_id: $to_id, user_id: $uid}})
                MERGE (a)-[r:{rel_type_upper}]->(b)
                SET r.description = $desc, r.relation_type = $rel_type, r.pg_id = $pg_id
                """,
                from_id=from_entry_id, to_id=to_entry_id, uid=uid,
                desc=description or '', rel_type=relation_type, pg_id=row['id']
            )
        except Exception as e:
            log.error(f"Neo4j link failed: {e}")

        return {
            'success': True,
            'relation_id': row['id'],
            'from': f'[{from_entry_id}] {from_entry["title"]}',
            'relation': relation_type,
            'to': f'[{to_entry_id}] {to_entry["title"]}',
            'description': description
        }
    except Exception as e:
        conn.rollback()
        return {'error': str(e)}
    finally:
        conn.close()


@mcp.tool()
def get_related(
    entry_id: int,
    relation_type: Optional[str] = None,
    direction: str = 'both'
) -> Dict:
    """Neo4j neighbors by direction; PG fallback."""
    uid = _get_uid()
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT id, title FROM entries WHERE id = %s AND user_id = %s",
                (entry_id, uid)
            )
            entry = cur.fetchone()
            if not entry:
                return {'error': f'Entry {entry_id} not found'}

        outgoing = []
        incoming = []

        try:
            if direction in ('outgoing', 'both'):
                rel_filter = f"AND r.relation_type = '{relation_type}'" if relation_type else ""
                rows = neo4j_read(
                    f"""
                    MATCH (a:Entry {{entry_id: $eid, user_id: $uid}})-[r]->(b:Entry)
                    WHERE type(r) <> 'BELONGS_TO' {rel_filter}
                    RETURN r.relation_type as relation_type, r.description as description,
                           b.entry_id as entry_id, b.title as title,
                           b.description as entry_desc, b.category_path as category_path
                    """,
                    eid=entry_id, uid=uid
                )
                outgoing = [{
                    'relation_type': r['relation_type'],
                    'description': r['description'],
                    'entry_id': r['entry_id'],
                    'title': r['title'],
                    'entry_description': r['entry_desc'],
                    'category_path': r['category_path']
                } for r in rows]

            if direction in ('incoming', 'both'):
                rel_filter = f"AND r.relation_type = '{relation_type}'" if relation_type else ""
                rows = neo4j_read(
                    f"""
                    MATCH (a:Entry)-[r]->(b:Entry {{entry_id: $eid, user_id: $uid}})
                    WHERE type(r) <> 'BELONGS_TO' {rel_filter}
                    RETURN r.relation_type as relation_type, r.description as description,
                           a.entry_id as entry_id, a.title as title,
                           a.description as entry_desc, a.category_path as category_path
                    """,
                    eid=entry_id, uid=uid
                )
                incoming = [{
                    'relation_type': r['relation_type'],
                    'description': r['description'],
                    'entry_id': r['entry_id'],
                    'title': r['title'],
                    'entry_description': r['entry_desc'],
                    'category_path': r['category_path']
                } for r in rows]
        except Exception as e:
            log.error(f"Neo4j get_related failed, falling back to PG: {e}")
            return _get_related_pg(entry_id, entry['title'], relation_type, direction, uid)

        return {
            'entry_id': entry_id,
            'entry_title': entry['title'],
            'outgoing_count': len(outgoing),
            'incoming_count': len(incoming),
            'outgoing': outgoing,
            'incoming': incoming
        }
    finally:
        conn.close()


def _get_related_pg(entry_id, entry_title, relation_type, direction, uid):
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            type_filter = "AND r.relation_type = %s" if relation_type else ""
            params_base = [entry_id, uid] + ([relation_type] if relation_type else [])
            outgoing = []
            incoming = []
            if direction in ('outgoing', 'both'):
                cur.execute(f"""
                    SELECT r.relation_type, r.description, e.id, e.title, e.description as entry_desc, c.path as category_path
                    FROM relations r JOIN entries e ON e.id = r.to_entry_id JOIN categories c ON c.id = e.category_id
                    WHERE r.from_entry_id = %s AND r.user_id = %s {type_filter}
                """, params_base)
                outgoing = [{'relation_type': r['relation_type'], 'description': r['description'],
                             'entry_id': r['id'], 'title': r['title'], 'entry_description': r['entry_desc'],
                             'category_path': r['category_path']} for r in cur.fetchall()]
            if direction in ('incoming', 'both'):
                cur.execute(f"""
                    SELECT r.relation_type, r.description, e.id, e.title, e.description as entry_desc, c.path as category_path
                    FROM relations r JOIN entries e ON e.id = r.from_entry_id JOIN categories c ON c.id = e.category_id
                    WHERE r.to_entry_id = %s AND r.user_id = %s {type_filter}
                """, params_base)
                incoming = [{'relation_type': r['relation_type'], 'description': r['description'],
                             'entry_id': r['id'], 'title': r['title'], 'entry_description': r['entry_desc'],
                             'category_path': r['category_path']} for r in cur.fetchall()]
        return {'entry_id': entry_id, 'entry_title': entry_title, 'outgoing_count': len(outgoing),
                'incoming_count': len(incoming), 'outgoing': outgoing, 'incoming': incoming, '_fallback': 'postgresql'}
    finally:
        conn.close()


@mcp.tool()
def unlink_entries(
    from_entry_id: int,
    to_entry_id: int,
    relation_type: Optional[str] = None
) -> Dict:
    """DELETE PG relations; optional type filter else all pair edges."""
    uid = _get_uid()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if relation_type:
                cur.execute(
                    "DELETE FROM relations WHERE from_entry_id = %s AND to_entry_id = %s AND relation_type = %s AND user_id = %s RETURNING id",
                    (from_entry_id, to_entry_id, relation_type, uid)
                )
            else:
                cur.execute(
                    "DELETE FROM relations WHERE from_entry_id = %s AND to_entry_id = %s AND user_id = %s RETURNING id",
                    (from_entry_id, to_entry_id, uid)
                )
            deleted = cur.fetchall()
            conn.commit()

        try:
            if relation_type:
                rel_type_upper = relation_type.upper()
                neo4j_write(
                    f"""
                    MATCH (a:Entry {{entry_id: $from_id, user_id: $uid}})-[r:{rel_type_upper}]->(b:Entry {{entry_id: $to_id, user_id: $uid}})
                    DELETE r
                    """,
                    from_id=from_entry_id, to_id=to_entry_id, uid=uid
                )
            else:
                neo4j_write(
                    """
                    MATCH (a:Entry {entry_id: $from_id, user_id: $uid})-[r]->(b:Entry {entry_id: $to_id, user_id: $uid})
                    WHERE type(r) <> 'BELONGS_TO'
                    DELETE r
                    """,
                    from_id=from_entry_id, to_id=to_entry_id, uid=uid
                )
        except Exception as e:
            log.error(f"Neo4j unlink failed: {e}")

        return {
            'success': True,
            'deleted_count': len(deleted),
            'from_entry_id': from_entry_id,
            'to_entry_id': to_entry_id
        }
    except Exception as e:
        conn.rollback()
        return {'error': str(e)}
    finally:
        conn.close()


@mcp.tool()
def get_graph(entry_id: int, depth: int = 2) -> Dict:
    """Variable-length Entry walk; depth capped 4; PG fallback."""
    uid = _get_uid()
    depth = min(depth, 4)

    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT id, title FROM entries WHERE id = %s AND user_id = %s",
                (entry_id, uid)
            )
            if not cur.fetchone():
                return {'error': f'Entry {entry_id} not found'}
    finally:
        conn.close()

    try:
        rows = neo4j_read(
            """
            MATCH path = (start:Entry {entry_id: $eid, user_id: $uid})-[*1..$depth]-(connected:Entry {user_id: $uid})
            WHERE ALL(r IN relationships(path) WHERE type(r) <> 'BELONGS_TO' AND type(r) <> 'CHILD_OF')
            UNWIND nodes(path) AS n
            WITH DISTINCT n
            WHERE n:Entry AND n.user_id = $uid
            RETURN n.entry_id AS entry_id, n.title AS title, n.category_path AS category_path
            """,
            eid=entry_id, uid=uid, depth=depth
        )
        nodes = {r['entry_id']: {'id': r['entry_id'], 'title': r['title'], 'category_path': r['category_path']} for r in rows}

        edge_rows = neo4j_read(
            """
            MATCH path = (start:Entry {entry_id: $eid, user_id: $uid})-[*1..$depth]-(connected:Entry {user_id: $uid})
            WHERE ALL(r IN relationships(path) WHERE type(r) <> 'BELONGS_TO' AND type(r) <> 'CHILD_OF')
            UNWIND relationships(path) AS rel
            WITH DISTINCT rel
            WHERE type(rel) <> 'BELONGS_TO' AND type(rel) <> 'CHILD_OF'
            RETURN startNode(rel).entry_id AS from_id, endNode(rel).entry_id AS to_id,
                   rel.relation_type AS type, rel.description AS description
            """,
            eid=entry_id, uid=uid, depth=depth
        )
        edges = [{'from': r['from_id'], 'to': r['to_id'], 'type': r['type'], 'description': r['description']} for r in edge_rows]

        return {
            'start_entry_id': entry_id,
            'depth': depth,
            'node_count': len(nodes),
            'edge_count': len(edges),
            'nodes': list(nodes.values()),
            'edges': edges
        }
    except Exception as e:
        log.error(f"Neo4j get_graph failed, falling back to PG: {e}")
        return _get_graph_pg(entry_id, depth, uid)


def _get_graph_pg(entry_id, depth, uid):
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            visited = set()
            queue = [entry_id]
            nodes = {}
            edges = []
            for _ in range(depth):
                if not queue:
                    break
                current_batch = [q for q in queue if q not in visited]
                if not current_batch:
                    break
                for eid in current_batch:
                    visited.add(eid)
                queue = []
                placeholders = ','.join(['%s'] * len(current_batch))
                cur.execute(f"""
                    SELECT e.id, e.title, c.path as category_path
                    FROM entries e JOIN categories c ON c.id = e.category_id
                    WHERE e.id IN ({placeholders}) AND e.user_id = %s
                """, current_batch + [uid])
                for r in cur.fetchall():
                    nodes[r['id']] = {'id': r['id'], 'title': r['title'], 'category_path': r['category_path']}
                cur.execute(f"""
                    SELECT from_entry_id, to_entry_id, relation_type, description
                    FROM relations WHERE from_entry_id IN ({placeholders}) AND user_id = %s
                """, current_batch + [uid])
                for r in cur.fetchall():
                    edge = {'from': r['from_entry_id'], 'to': r['to_entry_id'],
                            'type': r['relation_type'], 'description': r['description']}
                    if edge not in edges:
                        edges.append(edge)
                    if r['to_entry_id'] not in visited:
                        queue.append(r['to_entry_id'])
        return {'start_entry_id': entry_id, 'depth': depth, 'node_count': len(nodes),
                'edge_count': len(edges), 'nodes': list(nodes.values()), 'edges': edges, '_fallback': 'postgresql'}
    finally:
        conn.close()


@mcp.tool()
def find_paths(
    from_entry_id: int,
    to_entry_id: int,
    max_depth: int = 5
) -> Dict:
    """allShortestPaths between ids; max_depth capped 8."""
    uid = _get_uid()
    max_depth = min(max_depth, 8)

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, title FROM entries WHERE id IN (%s, %s) AND user_id = %s", (from_entry_id, to_entry_id, uid))
            found = cur.fetchall()
            if len(found) < 2:
                return {'error': 'One or both entries not found'}
    finally:
        conn.close()

    try:
        rows = neo4j_read(
            """
            MATCH path = allShortestPaths(
                (a:Entry {entry_id: $from_id, user_id: $uid})-[*1..$max_depth]-(b:Entry {entry_id: $to_id, user_id: $uid})
            )
            WHERE ALL(r IN relationships(path) WHERE type(r) <> 'BELONGS_TO' AND type(r) <> 'CHILD_OF')
            RETURN [n IN nodes(path) | {entry_id: n.entry_id, title: n.title}] AS path_nodes,
                   [r IN relationships(path) | {type: r.relation_type, description: r.description}] AS path_rels,
                   length(path) AS path_length
            ORDER BY path_length
            LIMIT 10
            """,
            from_id=from_entry_id, to_id=to_entry_id, uid=uid, max_depth=max_depth
        )

        paths = []
        for r in rows:
            paths.append({
                'nodes': r['path_nodes'],
                'relations': r['path_rels'],
                'length': r['path_length']
            })

        return {
            'from_entry_id': from_entry_id,
            'to_entry_id': to_entry_id,
            'path_count': len(paths),
            'paths': paths
        }
    except Exception as e:
        return {'error': f'Graph query failed: {str(e)}'}


@mcp.tool()
def find_pattern(description: str, limit: int = 20) -> Dict:
    """Heuristic NL→Cypher presets inside implementation."""
    uid = _get_uid()
    limit = min(limit, 50)
    desc_lower = description.lower()

    try:
        if 'orphan' in desc_lower or 'no relation' in desc_lower or 'isolated' in desc_lower:
            rows = neo4j_read(
                """
                MATCH (e:Entry {user_id: $uid})
                WHERE NOT (e)-[]-(:Entry)
                   OR ALL(r IN [(e)-[r]-() | r] WHERE type(r) = 'BELONGS_TO')
                RETURN e.entry_id AS entry_id, e.title AS title, e.category_path AS category_path
                LIMIT $limit
                """,
                uid=uid, limit=limit
            )
            return {'pattern': 'orphan_entries', 'count': len(rows),
                    'entries': [dict(r) for r in rows]}

        if 'most connected' in desc_lower or 'hub' in desc_lower:
            rows = neo4j_read(
                """
                MATCH (e:Entry {user_id: $uid})-[r]-(:Entry)
                WHERE type(r) <> 'BELONGS_TO' AND type(r) <> 'CHILD_OF'
                RETURN e.entry_id AS entry_id, e.title AS title, e.category_path AS category_path,
                       count(r) AS connection_count
                ORDER BY connection_count DESC
                LIMIT $limit
                """,
                uid=uid, limit=limit
            )
            return {'pattern': 'most_connected', 'count': len(rows),
                    'entries': [dict(r) for r in rows]}

        if 'connected to entry' in desc_lower or 'connected to #' in desc_lower:
            import re
            match = re.search(r'(?:entry|#)\s*(\d+)', desc_lower)
            if match:
                target_id = int(match.group(1))
                rows = neo4j_read(
                    """
                    MATCH (a:Entry {entry_id: $tid, user_id: $uid})-[r]-(b:Entry {user_id: $uid})
                    WHERE type(r) <> 'BELONGS_TO' AND type(r) <> 'CHILD_OF'
                    RETURN b.entry_id AS entry_id, b.title AS title, b.category_path AS category_path,
                           r.relation_type AS relation_type
                    LIMIT $limit
                    """,
                    tid=target_id, uid=uid, limit=limit
                )
                return {'pattern': f'connected_to_{target_id}', 'count': len(rows),
                        'entries': [dict(r) for r in rows]}

        relation_types = ['deployed_on', 'depends_on', 'used_by', 'part_of', 'supersedes',
                          'references', 'runs_on', 'owned_by', 'related_to', 'implements']
        for rt in relation_types:
            if rt in desc_lower:
                rt_upper = rt.upper()
                rows = neo4j_read(
                    f"""
                    MATCH (a:Entry {{user_id: $uid}})-[r:{rt_upper}]->(b:Entry {{user_id: $uid}})
                    RETURN a.entry_id AS from_id, a.title AS from_title,
                           b.entry_id AS to_id, b.title AS to_title,
                           r.description AS description
                    LIMIT $limit
                    """,
                    uid=uid, limit=limit
                )
                return {'pattern': f'relation_{rt}', 'count': len(rows),
                        'relations': [dict(r) for r in rows]}

        rows = neo4j_read(
            """
            MATCH (e:Entry {user_id: $uid})
            WHERE toLower(e.title) CONTAINS $search OR toLower(e.description) CONTAINS $search
            OPTIONAL MATCH (e)-[r]-(:Entry)
            WHERE type(r) <> 'BELONGS_TO' AND type(r) <> 'CHILD_OF'
            RETURN e.entry_id AS entry_id, e.title AS title, e.category_path AS category_path,
                   count(r) AS connections
            ORDER BY connections DESC
            LIMIT $limit
            """,
            uid=uid, search=desc_lower, limit=limit
        )
        return {'pattern': 'text_search_with_graph', 'count': len(rows),
                'entries': [dict(r) for r in rows]}
    except Exception as e:
        return {'error': f'Pattern query failed: {str(e)}'}


@mcp.tool()
def suggest_related(entry_id: int, limit: int = 10) -> Dict:
    """2-hop suggestions excluding direct neighbors."""
    uid = _get_uid()

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM entries WHERE id = %s AND user_id = %s", (entry_id, uid))
            if not cur.fetchone():
                return {'error': f'Entry {entry_id} not found'}
    finally:
        conn.close()

    try:
        rows = neo4j_read(
            """
            MATCH (start:Entry {entry_id: $eid, user_id: $uid})-[r1]-(mid:Entry {user_id: $uid})-[r2]-(suggestion:Entry {user_id: $uid})
            WHERE suggestion.entry_id <> $eid
              AND type(r1) <> 'BELONGS_TO' AND type(r1) <> 'CHILD_OF'
              AND type(r2) <> 'BELONGS_TO' AND type(r2) <> 'CHILD_OF'
              AND NOT (start)-[]-(suggestion)
            WITH suggestion, count(DISTINCT mid) AS shared_connections,
                 collect(DISTINCT mid.title)[..3] AS via_entries
            RETURN suggestion.entry_id AS entry_id, suggestion.title AS title,
                   suggestion.category_path AS category_path,
                   suggestion.description AS description,
                   shared_connections, via_entries
            ORDER BY shared_connections DESC
            LIMIT $limit
            """,
            eid=entry_id, uid=uid, limit=limit
        )

        return {
            'entry_id': entry_id,
            'suggestion_count': len(rows),
            'suggestions': [dict(r) for r in rows]
        }
    except Exception as e:
        return {'error': f'Suggestion query failed: {str(e)}'}


@mcp.tool()
def graph_stats() -> Dict:
    """Counts, orphans, top degree, rel-type histogram."""
    uid = _get_uid()

    try:
        total_nodes = neo4j_read(
            "MATCH (e:Entry {user_id: $uid}) RETURN count(e) AS count",
            uid=uid
        )
        total_edges = neo4j_read(
            """
            MATCH (a:Entry {user_id: $uid})-[r]->(b:Entry {user_id: $uid})
            WHERE type(r) <> 'BELONGS_TO' AND type(r) <> 'CHILD_OF'
            RETURN count(r) AS count
            """,
            uid=uid
        )

        top_connected = neo4j_read(
            """
            MATCH (e:Entry {user_id: $uid})-[r]-(:Entry)
            WHERE type(r) <> 'BELONGS_TO' AND type(r) <> 'CHILD_OF'
            RETURN e.entry_id AS entry_id, e.title AS title, count(r) AS connections
            ORDER BY connections DESC
            LIMIT 10
            """,
            uid=uid
        )

        relation_types = neo4j_read(
            """
            MATCH (a:Entry {user_id: $uid})-[r]->(b:Entry {user_id: $uid})
            WHERE type(r) <> 'BELONGS_TO' AND type(r) <> 'CHILD_OF'
            RETURN r.relation_type AS relation_type, count(r) AS count
            ORDER BY count DESC
            """,
            uid=uid
        )

        orphans = neo4j_read(
            """
            MATCH (e:Entry {user_id: $uid})
            WHERE NOT EXISTS { (e)-[r]-(:Entry) WHERE type(r) <> 'BELONGS_TO' AND type(r) <> 'CHILD_OF' }
            RETURN count(e) AS count
            """,
            uid=uid
        )

        return {
            'total_nodes': total_nodes[0]['count'] if total_nodes else 0,
            'total_edges': total_edges[0]['count'] if total_edges else 0,
            'orphan_nodes': orphans[0]['count'] if orphans else 0,
            'top_connected': [dict(r) for r in top_connected],
            'relation_types': [dict(r) for r in relation_types]
        }
    except Exception as e:
        return {'error': f'Graph stats failed: {str(e)}'}

