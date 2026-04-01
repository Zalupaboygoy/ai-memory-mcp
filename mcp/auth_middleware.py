"""Bearer token ASGI middleware."""
import asyncio

from user_context import _current_is_admin, _current_user_id
from db import _resolve_token


class AuthMiddlewareASGI:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] not in ('http', 'websocket'):
            await self.app(scope, receive, send)
            return
        headers = dict(scope.get('headers', []))
        auth = headers.get(b'authorization', b'').decode()
        if not auth.startswith('Bearer '):
            await self._send_401(scope, send)
            return
        token_raw = auth[7:]
        loop = asyncio.get_event_loop()
        user_id, is_admin = await loop.run_in_executor(None, _resolve_token, token_raw)
        if user_id is None:
            await self._send_401(scope, send)
            return
        tok_uid = _current_user_id.set(user_id)
        tok_admin = _current_is_admin.set(is_admin)
        try:
            await self.app(scope, receive, send)
        finally:
            _current_user_id.reset(tok_uid)
            _current_is_admin.reset(tok_admin)

    async def _send_401(self, scope, send):
        if scope['type'] == 'http':
            body = b'{"error":"Unauthorized"}'
            await send({'type': 'http.response.start', 'status': 401,
                        'headers': [(b'content-type', b'application/json'),
                                    (b'content-length', str(len(body)).encode())]})
            await send({'type': 'http.response.body', 'body': body, 'more_body': False})
        elif scope['type'] == 'websocket':
            await send({'type': 'websocket.close', 'code': 4401})
