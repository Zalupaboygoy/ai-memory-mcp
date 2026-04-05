"""ASGI middleware: accept `args` as an alias for MCP `arguments` in tools/call bodies.

Implemented as plain ASGI (not Starlette BaseHTTPMiddleware) so SSE/streaming responses
from FastMCP are not wrapped in a body consumer that triggers AssertionError on /sse.
"""
import json
from typing import Callable


def _merge_args_into_arguments(d: dict) -> bool:
    if 'args' not in d:
        return False
    args = d.pop('args')
    arguments = d.get('arguments')
    if not arguments:
        d['arguments'] = args
    return True


def _normalize_payload(data) -> bool:
    changed = False
    if isinstance(data, list):
        for item in data:
            if _normalize_payload(item):
                changed = True
        return changed
    if not isinstance(data, dict):
        return False
    params = data.get('params')
    if isinstance(params, dict):
        if _merge_args_into_arguments(params):
            changed = True
    return changed


async def _read_request_body(receive: Callable) -> bytes:
    body = b''
    more = True
    while more:
        message = await receive()
        if message['type'] != 'http.request':
            break
        body += message.get('body', b'')
        more = message.get('more_body', False)
    return body


class ArgsAliasMiddleware:
    """Map `params.args` -> `params.arguments` when `arguments` is missing or empty."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            await self.app(scope, receive, send)
            return

        method = scope.get('method', '')
        if method not in ('POST', 'PUT', 'PATCH'):
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get('headers', []))
        ct = headers.get(b'content-type', b'').decode('latin-1').lower()
        if 'application/json' not in ct:
            await self.app(scope, receive, send)
            return

        body = await _read_request_body(receive)
        if not body:
            async def empty_receive():
                return {'type': 'http.request', 'body': b'', 'more_body': False}

            await self.app(scope, empty_receive, send)
            return

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            async def replay_receive():
                return {'type': 'http.request', 'body': body, 'more_body': False}

            await self.app(scope, replay_receive, send)
            return

        if not isinstance(data, (dict, list)) or not _normalize_payload(data):
            async def replay_receive():
                return {'type': 'http.request', 'body': body, 'more_body': False}

            await self.app(scope, replay_receive, send)
            return

        new_body = json.dumps(data).encode('utf-8')
        new_headers = []
        found = False
        for k, v in scope.get('headers', []):
            if k.lower() == b'content-length':
                new_headers.append((k, str(len(new_body)).encode()))
                found = True
            else:
                new_headers.append((k, v))
        if not found:
            new_headers.append((b'content-length', str(len(new_body)).encode()))

        new_scope = {**scope, 'headers': new_headers}

        async def new_receive():
            return {'type': 'http.request', 'body': new_body, 'more_body': False}

        await self.app(new_scope, new_receive, send)
