"""Semantic ANN search. Full contract: project skill."""
from typing import Dict, Optional

import psycopg2.extras

from config import EMBEDDINGS_KEY
from db import get_conn
from embeddings import _get_embedding
from mcp_app import mcp
from user_context import _get_uid

@mcp.tool()
def semantic_search(
    query: str,
    category_path: Optional[str] = None,
    limit: int = 10
) -> Dict:
    """pgvector cosine; needs EMBEDDINGS_KEY or returns error."""
    uid = _get_uid()
    if not EMBEDDINGS_KEY:
        return {'error': 'Semantic search not available. EMBEDDINGS_KEY not configured.'}

    embedding = _get_embedding(query)
    if not embedding:
        return {'error': 'Failed to generate query embedding. Check EMBEDDINGS_KEY.'}

    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            conditions = ["e.user_id = %s", "e.embedding IS NOT NULL"]
            params = [uid]

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
                SELECT e.id, e.title, e.keywords, e.description,
                       e.importance_score, e.created_at, e.updated_at,
                       c.path as category_path, c.name as category_name,
                       1 - (e.embedding <=> %s::vector) as similarity
                FROM entries e
                JOIN categories c ON c.id = e.category_id
                {where}
                ORDER BY e.embedding <=> %s::vector
                LIMIT %s
            """, [str(embedding)] + params + [str(embedding), limit])
            results = cur.fetchall()

        return {
            'query': query,
            'search_type': 'semantic',
            'result_count': len(results),
            'results': [{
                'id': r['id'],
                'title': r['title'],
                'keywords': r['keywords'],
                'description': r['description'],
                'similarity': round(float(r['similarity']), 4),
                'category_path': r['category_path'],
                'created_at': str(r['created_at'])
            } for r in results]
        }
    finally:
        conn.close()

