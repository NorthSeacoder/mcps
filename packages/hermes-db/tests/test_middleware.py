import json

import anyio
import pytest

from hermes_db_mcp.config import settings
from hermes_db_mcp.middleware import BearerAuthMiddleware


def _http_scope(headers: list[tuple[bytes, bytes]] | None = None):
    return {
        "type": "http",
        "method": "POST",
        "path": "/mcp",
        "headers": headers or [],
    }


async def _receive():
    return {"type": "http.request", "body": b"", "more_body": False}


async def _collect(app, scope):
    messages = []

    async def send(message):
        messages.append(message)

    await app(scope, _receive, send)
    return messages


async def _collect_first(app, scope, count: int):
    messages = []

    async def send(message):
        messages.append(message)
        if len(messages) >= count:
            raise anyio.get_cancelled_exc_class()

    with pytest.raises(anyio.get_cancelled_exc_class()):
        await app(scope, _receive, send)
    return messages


def _headers(start_message):
    return {name.lower(): value for name, value in start_message.get("headers", [])}


@pytest.fixture(autouse=True)
def reset_api_token():
    original = settings.api_token
    settings.api_token = "test-token"
    yield
    settings.api_token = original


@pytest.mark.asyncio
async def test_rejects_missing_bearer_token_with_json_response():
    async def app(scope, receive, send):
        raise AssertionError("unauthorized requests must not reach wrapped app")

    messages = await _collect(BearerAuthMiddleware(app), _http_scope())

    assert messages[0]["status"] == 401
    assert _headers(messages[0])[b"content-type"].startswith(b"application/json")
    assert json.loads(messages[1]["body"]) == {"error": "unauthorized"}


@pytest.mark.asyncio
async def test_authorized_request_passes_through_success_response():
    async def app(scope, receive, send):
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"application/json")],
            }
        )
        await send({"type": "http.response.body", "body": b'{"ok":true}'})

    messages = await _collect(
        BearerAuthMiddleware(app),
        _http_scope([(b"authorization", b"Bearer test-token")]),
    )

    assert messages[0]["status"] == 200
    assert messages[1]["body"] == b'{"ok":true}'


@pytest.mark.asyncio
async def test_authorized_mcp_path_with_trailing_slash_is_normalized():
    seen_paths = []

    async def app(scope, receive, send):
        seen_paths.append((scope["path"], scope["raw_path"]))
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"application/json")],
            }
        )
        await send({"type": "http.response.body", "body": b'{"ok":true}'})

    scope = _http_scope([(b"authorization", b"Bearer test-token")])
    scope["path"] = "/mcp/"
    scope["raw_path"] = b"/mcp/"

    messages = await _collect(BearerAuthMiddleware(app), scope)

    assert seen_paths == [("/mcp", b"/mcp")]
    assert messages[0]["status"] == 200
    assert _headers(messages[0])[b"content-type"] == b"application/json"


@pytest.mark.asyncio
async def test_authorized_stream_probe_returns_event_stream_headers():
    async def app(scope, receive, send):
        raise AssertionError("GET stream probes are handled by middleware")

    scope = _http_scope(
        [
            (b"authorization", b"Bearer test-token"),
            (b"accept", b"application/json, text/event-stream"),
        ]
    )
    scope["method"] = "GET"

    messages = await _collect_first(BearerAuthMiddleware(app), scope, 2)

    assert messages[0]["status"] == 200
    assert _headers(messages[0])[b"content-type"].startswith(b"text/event-stream")
    assert messages[1]["body"].startswith(b": keepalive")
    assert messages[1]["more_body"] is True


@pytest.mark.asyncio
async def test_authorized_get_probe_without_event_stream_accept_returns_json():
    async def app(scope, receive, send):
        raise AssertionError("GET probes are handled by middleware")

    scope = _http_scope(
        [
            (b"authorization", b"Bearer test-token"),
            (b"accept", b"*/*"),
        ]
    )
    scope["method"] = "GET"

    messages = await _collect(BearerAuthMiddleware(app), scope)

    assert messages[0]["status"] == 200
    assert _headers(messages[0])[b"content-type"] == b"application/json"
    assert json.loads(messages[1]["body"]) == {"ok": True}


@pytest.mark.asyncio
async def test_authorized_head_probe_returns_empty_json_headers():
    async def app(scope, receive, send):
        raise AssertionError("HEAD probes are handled by middleware")

    scope = _http_scope([(b"authorization", b"Bearer test-token")])
    scope["method"] = "HEAD"

    messages = await _collect(BearerAuthMiddleware(app), scope)

    assert messages[0]["status"] == 200
    assert _headers(messages[0])[b"content-type"] == b"application/json"
    assert _headers(messages[0])[b"content-length"] == b"0"
    assert messages[1]["body"] == b""


@pytest.mark.asyncio
async def test_unauthorized_head_probe_returns_empty_401_headers():
    async def app(scope, receive, send):
        raise AssertionError("HEAD probes are handled by middleware")

    scope = _http_scope()
    scope["method"] = "HEAD"

    messages = await _collect(BearerAuthMiddleware(app), scope)

    assert messages[0]["status"] == 401
    assert _headers(messages[0])[b"content-type"] == b"application/json"
    assert _headers(messages[0])[b"content-length"] == b"0"
    assert messages[1]["body"] == b""


@pytest.mark.asyncio
async def test_authorized_unsupported_mcp_method_returns_json_error():
    async def app(scope, receive, send):
        raise AssertionError("unsupported /mcp methods are handled by middleware")

    scope = _http_scope([(b"authorization", b"Bearer test-token")])
    scope["method"] = "OPTIONS"

    messages = await _collect(BearerAuthMiddleware(app), scope)

    assert messages[0]["status"] == 405
    assert _headers(messages[0])[b"content-type"] == b"application/json"
    assert _headers(messages[0])[b"allow"] == b"GET, POST"
    assert messages[1]["body"] == b'{"error":"method_not_allowed"}'


@pytest.mark.asyncio
async def test_empty_error_response_gets_json_body_and_content_type():
    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": 404, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    messages = await _collect(
        BearerAuthMiddleware(app),
        _http_scope([(b"authorization", b"Bearer test-token")]),
    )

    assert messages[0]["status"] == 404
    assert _headers(messages[0])[b"content-type"] == b"application/json"
    assert json.loads(messages[1]["body"]) == {"error": "not_found"}


@pytest.mark.asyncio
async def test_streamed_empty_error_response_gets_single_json_response_start():
    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": 404, "headers": []})
        await send({"type": "http.response.body", "body": b"", "more_body": True})
        await send({"type": "http.response.body", "body": b"", "more_body": False})

    messages = await _collect(
        BearerAuthMiddleware(app),
        _http_scope([(b"authorization", b"Bearer test-token")]),
    )

    starts = [
        message for message in messages if message["type"] == "http.response.start"
    ]
    assert len(starts) == 1
    assert starts[0]["status"] == 404
    assert _headers(starts[0])[b"content-type"] == b"application/json"
    assert json.loads(messages[1]["body"]) == {"error": "not_found"}


@pytest.mark.asyncio
async def test_error_response_with_body_gets_content_type_when_missing():
    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": 406, "headers": []})
        await send({"type": "http.response.body", "body": b"not acceptable"})

    messages = await _collect(
        BearerAuthMiddleware(app),
        _http_scope([(b"authorization", b"Bearer test-token")]),
    )

    assert messages[0]["status"] == 406
    assert _headers(messages[0])[b"content-type"] == b"text/plain; charset=utf-8"
    assert messages[1]["body"] == b"not acceptable"


@pytest.mark.asyncio
async def test_success_response_without_content_type_gets_json_content_type():
    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    messages = await _collect(
        BearerAuthMiddleware(app),
        _http_scope([(b"authorization", b"Bearer test-token")]),
    )

    assert messages[0]["status"] == 200
    assert _headers(messages[0])[b"content-type"] == b"application/json"
    assert messages[1]["body"] == b""


@pytest.mark.asyncio
async def test_exception_before_response_start_gets_json_500():
    async def app(scope, receive, send):
        raise RuntimeError("boom")

    messages = await _collect(
        BearerAuthMiddleware(app),
        _http_scope([(b"authorization", b"Bearer test-token")]),
    )

    assert messages[0]["status"] == 500
    assert _headers(messages[0])[b"content-type"].startswith(b"application/json")
    assert json.loads(messages[1]["body"]) == {"error": "internal_server_error"}
