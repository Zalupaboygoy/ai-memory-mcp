"""Optional LLM / embedding API calls (Gemini-compatible)."""
from typing import List, Optional

import requests

from config import (
    EMBEDDINGS_KEY,
    EMBEDDINGS_MODEL,
    EMBEDDINGS_URL,
    LLM_CHAT_KEY,
    LLM_CHAT_MODEL,
    LLM_CHAT_URL,
)


def _get_embedding(text: str) -> Optional[List[float]]:
    if not EMBEDDINGS_KEY:
        return None
    try:
        url = f"{EMBEDDINGS_URL.rstrip('/')}/{EMBEDDINGS_MODEL}:embedContent"
        r = requests.post(
            url,
            headers={'Content-Type': 'application/json'},
            params={'key': EMBEDDINGS_KEY},
            json={'model': EMBEDDINGS_MODEL, 'content': {'parts': [{'text': text}]}},
            timeout=10
        )
        if r.ok:
            return r.json()['embedding']['values']
    except Exception:
        pass
    return None


def _llm_chat(system: str, user: str) -> Optional[str]:
    if not LLM_CHAT_URL or not LLM_CHAT_KEY:
        return None
    try:
        r = requests.post(
            f"{LLM_CHAT_URL.rstrip('/')}/chat/completions",
            headers={'Authorization': f'Bearer {LLM_CHAT_KEY}', 'Content-Type': 'application/json'},
            json={
                'model': LLM_CHAT_MODEL,
                'messages': [
                    {'role': 'system', 'content': system},
                    {'role': 'user', 'content': user}
                ],
                'max_tokens': 500
            },
            timeout=30
        )
        if r.ok:
            return r.json()['choices'][0]['message']['content']
    except Exception:
        pass
    return None
