"""KB CRUD/search. Full contract: project skill."""
import json
from typing import Any, Dict, List, Optional

import psycopg2.extras

from config import AUTO_SUMMARIZE, AUTO_SUMMARIZE_TRIGGER
from db import get_conn
from mcp_app import mcp
from neo4j_ops import (
    _delete_category_from_neo4j,
    _delete_entry_from_neo4j,
    _sync_category_to_neo4j,
    _sync_entry_to_neo4j,
)
from user_context import _get_uid

@mcp.tool()
def whoami() -> Dict:
    """Current user row + active token count."""
    uid = _get_uid()
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT id, username, is_admin, created_at FROM users WHERE id = %s", (uid,))
            user = cur.fetchone()
            cur.execute(
                "SELECT COUNT(*) as c FROM tokens WHERE user_id = %s AND (expires_at IS NULL OR expires_at > NOW())",
                (uid,)
            )
            tok_count = cur.fetchone()['c']
        return {
            'user_id': user['id'],
            'username': user['username'],
            'is_admin': user['is_admin'],
            'active_tokens': tok_count,
            'created_at': str(user['created_at'])
        }
    finally:
        conn.close()


def _get_root_paths(cur):
    cur.execute("SELECT path FROM categories WHERE parent_id IS NULL ORDER BY path")
    return [r['path'] for r in cur.fetchall()]


@mcp.tool()
def get_structure(depth: int = 2) -> Dict:
    """Category tree to depth; agent_hint/summary on nodes."""
    uid = _get_uid()
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                WITH RECURSIVE cat_tree AS (
                    SELECT id, parent_id, path, name, description, agent_hint, level, summary
                    FROM categories WHERE parent_id IS NULL AND user_id = %s
                    UNION ALL
                    SELECT c.id, c.parent_id, c.path, c.name, c.description, c.agent_hint, c.level, c.summary
                    FROM categories c
                    INNER JOIN cat_tree ct ON c.parent_id = ct.id
                    WHERE c.level < %s
                )
                SELECT ct.*, COUNT(e.id) as entry_count
                FROM cat_tree ct
                LEFT JOIN entries e ON e.category_id = ct.id AND e.user_id = %s
                GROUP BY ct.id, ct.parent_id, ct.path, ct.name, ct.description, ct.agent_hint, ct.level, ct.summary
                ORDER BY ct.path
            """, (uid, depth, uid))
            rows = cur.fetchall()

        def build_tree(rows, parent_id=None):
            result = []
            for row in rows:
                if row['parent_id'] == parent_id:
                    node = {
                        'path': row['path'],
                        'name': row['name'],
                        'description': row['description'],
                        'agent_hint': row['agent_hint'],
                        'level': row['level'],
                        'summary': row['summary'],
                        'entry_count': row['entry_count'],
                        'subcategories': build_tree(rows, row['id'])
                    }
                    result.append(node)
            return result

        tree = build_tree(rows)
        total_entries = sum(r['entry_count'] for r in rows)
        return {
            'total_entries': total_entries,
            'total_categories': len(rows),
            'depth_returned': depth,
            'categories': tree
        }
    finally:
        conn.close()


@mcp.tool()
def get_subcategories(category_path: str) -> Dict:
    """Direct children of category_path."""
    uid = _get_uid()
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT id FROM categories WHERE path = %s AND user_id = %s", (category_path, uid))
            parent = cur.fetchone()
            if not parent:
                return {'error': f'Category "{category_path}" not found', 'available_root_paths': _get_root_paths(cur)}
            cur.execute("""
                SELECT c.path, c.name, c.description, c.agent_hint, c.level, c.summary,
                       COUNT(e.id) as entry_count
                FROM categories c
                LEFT JOIN entries e ON e.category_id = c.id AND e.user_id = %s
                WHERE c.parent_id = %s
                GROUP BY c.id ORDER BY c.path
            """, (uid, parent['id']))
            subs = cur.fetchall()
        return {
            'parent_path': category_path,
            'subcategory_count': len(subs),
            'subcategories': [dict(s) for s in subs]
        }
    finally:
        conn.close()


@mcp.tool()
def search(
    query: str,
    category_path: Optional[str] = None,
    keywords: Optional[List[str]] = None,
    limit: int = 10
) -> Dict:
    """FTS plainto_tsquery + optional keywords[] AND + subtree category filter."""
    uid = _get_uid()
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            conditions = ["e.user_id = %s"]
            params = [uid]

            if query:
                conditions.append("""
                    to_tsvector('english', coalesce(e.title,'') || ' ' || coalesce(e.description,'') || ' ' || coalesce(e.content,''))
                    @@ plainto_tsquery('english', %s)
                """)
                params.append(query)

            if keywords:
                conditions.append("e.keywords && %s")
                params.append(keywords)

            if category_path:
                conditions.append("""
                    e.category_id IN (
                        SELECT id FROM categories
                        WHERE (path = %s OR path LIKE %s) AND user_id = %s
                    )
                """)
                params.extend([category_path, category_path + '.%', uid])

            where = 'WHERE ' + ' AND '.join(conditions)
            limit = min(limit, 50)

            cur.execute(f"""
                SELECT
                    e.id, e.title, e.keywords, e.description,
                    e.gitea_url, e.repo_visibility, e.repo_owner,
                    e.importance_score, e.metadata,
                    e.created_at, e.updated_at,
                    c.path as category_path, c.name as category_name,
                    CASE WHEN %s != '' THEN
                        ts_rank(
                            to_tsvector('english', coalesce(e.title,'') || ' ' || coalesce(e.description,'') || ' ' || coalesce(e.content,'')),
                            plainto_tsquery('english', %s)
                        )
                    ELSE e.importance_score END as rank
                FROM entries e
                JOIN categories c ON c.id = e.category_id
                {where}
                ORDER BY rank DESC, e.updated_at DESC
                LIMIT %s
            """, [query or '', query or ''] + params + [limit])

            results = cur.fetchall()

        return {
            'query': query,
            'category_filter': category_path,
            'keyword_filter': keywords,
            'result_count': len(results),
            'results': [
                {
                    **{k: v for k, v in dict(r).items() if k != 'rank'},
                    'created_at': str(r['created_at']),
                    'updated_at': str(r['updated_at']),
                }
                for r in results
            ]
        }
    finally:
        conn.close()


@mcp.tool()
def write_entry(
    category_path: str,
    title: str,
    keywords: List[str],
    description: str,
    content: Optional[str] = None,
    gitea_url: Optional[str] = None,
    repo_visibility: Optional[str] = None,
    repo_owner: Optional[str] = None,
    importance_score: float = 0.5,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict:
    """INSERT entry; category must exist; Neo4j sync; gitea_* validated if set."""
    uid = _get_uid()
    if repo_visibility and repo_visibility not in ('public', 'private'):
        return {'error': 'repo_visibility must be "public" or "private"'}

    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT id FROM categories WHERE path = %s AND user_id = %s", (category_path, uid))
            cat = cur.fetchone()
            if not cat:
                return {
                    'error': f'Category "{category_path}" not found. Create it first with create_category()',
                    'tip': 'Call get_structure() to see available categories'
                }
            cur.execute("""
                INSERT INTO entries
                    (user_id, category_id, title, keywords, description, content,
                     gitea_url, repo_visibility, repo_owner, importance_score, metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, created_at
            """, (
                uid, cat['id'], title, keywords, description, content,
                gitea_url, repo_visibility, repo_owner,
                importance_score, json.dumps(metadata or {})
            ))
            row = cur.fetchone()
            entry_id = row['id']
            conn.commit()

            should_auto = False
            if AUTO_SUMMARIZE:
                cur.execute(
                    "SELECT COUNT(*) as c FROM entries WHERE category_id = %s AND user_id = %s",
                    (cat['id'], uid)
                )
                count = cur.fetchone()['c']
                should_auto = (count % AUTO_SUMMARIZE_TRIGGER == 0)

        _sync_entry_to_neo4j(uid, entry_id, title, keywords, description, category_path, importance_score, metadata)

        result = {
            'success': True,
            'entry_id': entry_id,
            'category_path': category_path,
            'title': title,
            'created_at': str(row['created_at']),
            'tip': f'Remember to call update_summary("{category_path}", "...") to keep summaries current'
        }

        if should_auto:
            result['auto_summary_triggered'] = True

        return result
    except Exception as e:
        conn.rollback()
        return {'error': str(e)}
    finally:
        conn.close()


@mcp.tool()
def get_entry(entry_id: int) -> Dict:
    """SELECT by id; strips embedding vector."""
    uid = _get_uid()
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT e.*, c.path as category_path, c.name as category_name
                FROM entries e
                JOIN categories c ON c.id = e.category_id
                WHERE e.id = %s AND e.user_id = %s
            """, (entry_id, uid))
            row = cur.fetchone()
        if not row:
            return {'error': f'Entry {entry_id} not found'}
        r = dict(row)
        r['created_at'] = str(r['created_at'])
        r['updated_at'] = str(r['updated_at'])
        r.pop('embedding', None)
        return r
    finally:
        conn.close()


@mcp.tool()
def update_entry(
    entry_id: int,
    title: Optional[str] = None,
    keywords: Optional[List[str]] = None,
    description: Optional[str] = None,
    content: Optional[str] = None,
    gitea_url: Optional[str] = None,
    repo_visibility: Optional[str] = None,
    repo_owner: Optional[str] = None,
    importance_score: Optional[float] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict:
    """PATCH only provided columns; Neo4j resync."""
    uid = _get_uid()
    updates = {}
    if title is not None: updates['title'] = title
    if keywords is not None: updates['keywords'] = keywords
    if description is not None: updates['description'] = description
    if content is not None: updates['content'] = content
    if gitea_url is not None: updates['gitea_url'] = gitea_url
    if repo_visibility is not None: updates['repo_visibility'] = repo_visibility
    if repo_owner is not None: updates['repo_owner'] = repo_owner
    if importance_score is not None: updates['importance_score'] = importance_score
    if metadata is not None: updates['metadata'] = json.dumps(metadata)

    if not updates:
        return {'error': 'No fields provided to update'}

    set_clause = ', '.join(f"{k} = %s" for k in updates)
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"UPDATE entries SET {set_clause}, updated_at = NOW() WHERE id = %s AND user_id = %s RETURNING id",
                list(updates.values()) + [entry_id, uid]
            )
            if not cur.fetchone():
                return {'error': f'Entry {entry_id} not found'}
            conn.commit()

            cur.execute("""
                SELECT e.title, e.keywords, e.description, e.importance_score, e.metadata,
                       c.path as category_path
                FROM entries e JOIN categories c ON c.id = e.category_id
                WHERE e.id = %s AND e.user_id = %s
            """, (entry_id, uid))
            row = cur.fetchone()
            if row:
                _sync_entry_to_neo4j(
                    uid, entry_id, row['title'], row['keywords'],
                    row['description'], row['category_path'],
                    row['importance_score'], row['metadata'] if isinstance(row['metadata'], dict) else {}
                )

        return {'success': True, 'entry_id': entry_id, 'updated_fields': list(updates.keys())}
    except Exception as e:
        conn.rollback()
        return {'error': str(e)}
    finally:
        conn.close()


@mcp.tool()
def delete_entry(entry_id: int) -> Dict:
    """DELETE row + Neo4j Entry node."""
    uid = _get_uid()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM entries WHERE id = %s AND user_id = %s RETURNING id", (entry_id, uid))
            if not cur.fetchone():
                return {'error': f'Entry {entry_id} not found'}
            conn.commit()
        _delete_entry_from_neo4j(uid, entry_id)
        return {'success': True, 'deleted_entry_id': entry_id}
    except Exception as e:
        conn.rollback()
        return {'error': str(e)}
    finally:
        conn.close()


@mcp.tool()
def create_category(
    path: str,
    name: str,
    description: str,
    agent_hint: str
) -> Dict:
    """INSERT path; parent path must exist unless root."""
    uid = _get_uid()
    parts = path.split('.')
    level = len(parts) - 1
    parent_path = '.'.join(parts[:-1]) if level > 0 else None

    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            parent_id = None
            if parent_path:
                cur.execute("SELECT id FROM categories WHERE path = %s AND user_id = %s", (parent_path, uid))
                parent = cur.fetchone()
                if not parent:
                    return {'error': f'Parent category "{parent_path}" does not exist. Create it first.'}
                parent_id = parent['id']
            cur.execute("""
                INSERT INTO categories (user_id, parent_id, path, name, description, agent_hint, level)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (uid, parent_id, path, name, description, agent_hint, level))
            row = cur.fetchone()
            conn.commit()
        _sync_category_to_neo4j(uid, path, name, description)
        return {'success': True, 'category_id': row['id'], 'path': path, 'level': level}
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        return {'error': f'Category "{path}" already exists'}
    except Exception as e:
        conn.rollback()
        return {'error': str(e)}
    finally:
        conn.close()


@mcp.tool()
def delete_category(path: str, force: bool = False) -> Dict:
    """DELETE subtree path; force cascades entries/subcats."""
    uid = _get_uid()
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT id FROM categories WHERE path = %s AND user_id = %s", (path, uid))
            cat = cur.fetchone()
            if not cat:
                return {'error': f'Category "{path}" not found'}
            if not force:
                cur.execute("SELECT COUNT(*) as c FROM entries WHERE category_id = %s", (cat['id'],))
                if cur.fetchone()['c'] > 0:
                    return {'error': 'Category has entries. Use force=True to delete anyway.'}
                cur.execute("SELECT COUNT(*) as c FROM categories WHERE parent_id = %s", (cat['id'],))
                if cur.fetchone()['c'] > 0:
                    return {'error': 'Category has subcategories. Use force=True to delete anyway.'}
            cur.execute(
                "DELETE FROM categories WHERE (path = %s OR path LIKE %s) AND user_id = %s",
                (path, path + '.%', uid)
            )
            conn.commit()
        _delete_category_from_neo4j(uid, path)
        return {'success': True, 'deleted_path': path}
    except Exception as e:
        conn.rollback()
        return {'error': str(e)}
    finally:
        conn.close()


@mcp.tool()
def update_summary(category_path: str, summary_text: str) -> Dict:
    """Category summary + summaries table upsert."""
    uid = _get_uid()
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT id FROM categories WHERE path = %s AND user_id = %s", (category_path, uid))
            cat = cur.fetchone()
            if not cat:
                return {'error': f'Category "{category_path}" not found'}
            cur.execute(
                "UPDATE categories SET summary = %s, summary_updated_at = NOW() WHERE id = %s AND user_id = %s",
                (summary_text, cat['id'], uid)
            )
            cur.execute(
                "SELECT COUNT(*) as c FROM entries WHERE category_id = %s AND user_id = %s",
                (cat['id'], uid)
            )
            entry_count = cur.fetchone()['c']
            cur.execute("""
                INSERT INTO summaries (user_id, scope_type, scope_id, content, entries_count, generated_by, updated_at)
                VALUES (%s, 'category', %s, %s, %s, 'agent', NOW())
                ON CONFLICT (user_id, scope_type, COALESCE(scope_id, 0))
                DO UPDATE SET content = EXCLUDED.content,
                              entries_count = EXCLUDED.entries_count,
                              generated_by = 'agent',
                              updated_at = NOW()
            """, (uid, cat['id'], summary_text, entry_count))
            conn.commit()
        return {
            'success': True,
            'category_path': category_path,
            'entries_covered': entry_count
        }
    except Exception as e:
        conn.rollback()
        return {'error': str(e)}
    finally:
        conn.close()


@mcp.tool()
def update_global_summary(summary_text: str) -> Dict:
    """Global summaries upsert."""
    uid = _get_uid()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO summaries (user_id, scope_type, scope_id, content, generated_by, updated_at)
                VALUES (%s, 'global', NULL, %s, 'agent', NOW())
                ON CONFLICT (user_id, scope_type, COALESCE(scope_id, 0))
                DO UPDATE SET content = EXCLUDED.content,
                              generated_by = 'agent',
                              updated_at = NOW()
            """, (uid, summary_text))
            conn.commit()
        return {'success': True, 'type': 'global'}
    except Exception as e:
        conn.rollback()
        return {'error': str(e)}
    finally:
        conn.close()


@mcp.tool()
def get_context(category_path: str, include_children: bool = True) -> Dict:
    """Summaries for path branch; optional subtree rollup."""
    uid = _get_uid()
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT id, path, name, description, summary, summary_updated_at,
                       (SELECT COUNT(*) FROM entries e WHERE e.category_id = categories.id AND e.user_id = %s) as entry_count
                FROM categories
                WHERE (path = %s OR (path LIKE %s AND %s = TRUE)) AND user_id = %s
                ORDER BY path
            """, (uid, category_path, category_path + '.%', include_children, uid))
            rows = cur.fetchall()

        if not rows:
            return {'error': f'Category "{category_path}" not found'}

        return {
            'category_path': category_path,
            'categories': [{
                'path': r['path'],
                'name': r['name'],
                'description': r['description'],
                'summary': r['summary'],
                'entry_count': r['entry_count'],
                'summary_updated_at': str(r['summary_updated_at']) if r['summary_updated_at'] else None
            } for r in rows],
            'total_entries': sum(r['entry_count'] for r in rows)
        }
    finally:
        conn.close()


@mcp.tool()
def get_global_context() -> Dict:
    """Global summary + root category rollups + total entry count."""
    uid = _get_uid()
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT content, updated_at FROM summaries WHERE user_id = %s AND scope_type = 'global'",
                (uid,)
            )
            global_row = cur.fetchone()

            cur.execute("""
                SELECT c.path, c.name, c.summary, c.summary_updated_at,
                       COUNT(e.id) as entry_count,
                       (SELECT COUNT(*) FROM categories sub WHERE sub.path LIKE c.path || '.%%' AND sub.user_id = %s) as subcategory_count
                FROM categories c
                LEFT JOIN entries e ON e.category_id = c.id AND e.user_id = %s
                WHERE c.parent_id IS NULL AND c.user_id = %s
                GROUP BY c.id ORDER BY c.path
            """, (uid, uid, uid))
            root_cats = cur.fetchall()

            cur.execute(
                "SELECT COUNT(*) as total FROM entries WHERE user_id = %s",
                (uid,)
            )
            total = cur.fetchone()['total']

        return {
            'global_summary': global_row['content'] if global_row else None,
            'global_summary_updated': str(global_row['updated_at']) if global_row else None,
            'total_entries': total,
            'root_categories': [{
                'path': r['path'],
                'name': r['name'],
                'summary': r['summary'],
                'entry_count': r['entry_count'],
                'subcategory_count': r['subcategory_count'],
                'summary_updated_at': str(r['summary_updated_at']) if r['summary_updated_at'] else None
            } for r in root_cats]
        }
    finally:
        conn.close()

