"""ASGI middleware: accept `args` as an alias for MCP `arguments` in tools/call bodies."""
import json

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


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


class ArgsAliasMiddleware(BaseHTTPMiddleware):
    """Map `params.args` -> `params.arguments` when `arguments` is missing or empty."""

    async def dispatch(self, request: Request, call_next):
        if request.method not in ('POST', 'PUT', 'PATCH'):
            return await call_next(request)
        ct = request.headers.get('content-type', '').lower()
        if 'application/json' not in ct:
            return await call_next(request)
        body = await request.body()
        if not body:
            return await call_next(request)
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            return await call_next(request)
        if not isinstance(data, (dict, list)):
            return await call_next(request)
        if not _normalize_payload(data):
            return await call_next(request)

        new_body = json.dumps(data).encode('utf-8')
        async def receive():
            return {'type': 'http.request', 'body': new_body, 'more_body': False}

        scope = dict(request.scope)
        headers = []
        found = False
        for k, v in scope.get('headers', []):
            if k.lower() == b'content-length':
                headers.append((k, str(len(new_body)).encode()))
                found = True
            else:
                headers.append((k, v))
        if not found:
            headers.append((b'content-length', str(len(new_body)).encode()))
        scope['headers'] = headers
        return await call_next(Request(scope, receive))
