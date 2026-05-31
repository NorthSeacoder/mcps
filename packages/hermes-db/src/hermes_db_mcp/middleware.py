from http import HTTPStatus

import anyio
from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from hermes_db_mcp.config import settings


class BearerAuthMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        if not settings.api_token:
            await self._call_with_diagnostic_errors(scope, receive, send)
            return

        headers = Headers(scope=scope)
        auth_header = headers.get("authorization", "")
        if self._is_head_probe(scope):
            await self._send_empty_json_probe_response(send, status=200 if auth_header == f"Bearer {settings.api_token}" else 401)
            return

        if auth_header == f"Bearer {settings.api_token}":
            scope = self._normalize_mcp_path(scope)
            if self._is_stream_probe(scope):
                if self._accepts_event_stream(headers):
                    await self._send_empty_event_stream(send)
                else:
                    await self._send_json_probe_response(send)
                return
            if self._is_unsupported_mcp_method(scope):
                await self._send_json_method_not_allowed(send)
                return
            await self._call_with_diagnostic_errors(scope, receive, send)
            return

        response = JSONResponse({"error": "unauthorized"}, status_code=401)
        await response(scope, receive, send)

    def _normalize_mcp_path(self, scope: Scope) -> Scope:
        if scope.get("path") != "/mcp/":
            return scope

        normalized = dict(scope)
        normalized["path"] = "/mcp"
        normalized["raw_path"] = b"/mcp"
        return normalized

    def _is_stream_probe(self, scope: Scope) -> bool:
        return scope.get("method") == "GET" and scope.get("path") == "/mcp"

    def _is_head_probe(self, scope: Scope) -> bool:
        return scope.get("method") == "HEAD" and scope.get("path") == "/mcp"

    def _is_unsupported_mcp_method(self, scope: Scope) -> bool:
        return scope.get("path") == "/mcp" and scope.get("method") not in (
            "GET",
            "POST",
        )

    def _accepts_event_stream(self, headers: Headers) -> bool:
        return "text/event-stream" in headers.get("accept", "")

    async def _send_empty_json_probe_response(self, send: Send, status: int = 200) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", b"0"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": b""})

    async def _send_json_probe_response(self, send: Send) -> None:
        body = b'{"ok":true}'
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})

    async def _send_json_method_not_allowed(self, send: Send) -> None:
        body = b'{"error":"method_not_allowed"}'
        await send(
            {
                "type": "http.response.start",
                "status": 405,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                    (b"allow", b"GET, POST"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})

    async def _send_empty_event_stream(self, send: Send) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [
                    (b"content-type", b"text/event-stream; charset=utf-8"),
                    (b"cache-control", b"no-cache"),
                ],
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": b": keepalive\n\n",
                "more_body": True,
            }
        )
        while True:
            await anyio.sleep(30)
            await send(
                {
                    "type": "http.response.body",
                    "body": b": keepalive\n\n",
                    "more_body": True,
                }
            )

    async def _call_with_diagnostic_errors(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        state = _ResponseState()

        async def guarded_send(message: Message) -> None:
            if message["type"] == "http.response.start":
                state.capture_start(message)
                return

            if message["type"] == "http.response.body":
                body = message.get("body", b"")
                if state.should_replace_empty_error(message, body):
                    await send(state.start_with_json_headers)
                    await send(
                        {
                            "type": "http.response.body",
                            "body": state.fallback_body,
                            "more_body": False,
                        }
                    )
                    state.sent_start = True
                    return

                if state.should_buffer_empty_error_chunk(message, body):
                    return

                if body:
                    state.has_body = True

                if state.should_buffer_body_for_content_length(message):
                    state.body_chunks.append(body)
                    return

                if state.should_flush_buffered_body(message):
                    state.body_chunks.append(body)
                    buffered_body = b"".join(state.body_chunks)
                    await send(state.start_with_content_length(buffered_body))
                    await send(
                        {
                            "type": "http.response.body",
                            "body": buffered_body,
                            "more_body": False,
                        }
                    )
                    state.sent_start = True
                    return

                if not state.sent_start and state.start_message is not None:
                    start = (
                        state.start_with_content_length(body)
                        if state.should_add_content_length(message, body)
                        else state.start_with_diagnostic_headers
                    )
                    await send(start)
                    state.sent_start = True

            await send(message)

        try:
            await self.app(scope, receive, guarded_send)
        except Exception:
            if not state.sent_start:
                response = JSONResponse(
                    {"error": "internal_server_error"},
                    status_code=500,
                )
                await response(scope, receive, send)
                return
            raise

        if state.needs_empty_error_body and not state.sent_start:
            await send(state.start_with_json_headers)
            await send(
                {
                    "type": "http.response.body",
                    "body": state.fallback_body,
                    "more_body": False,
                }
            )
        elif not state.sent_start and state.start_message is not None:
            if state.body_chunks:
                body = b"".join(state.body_chunks)
                await send(state.start_with_content_length(body))
                await send(
                    {
                        "type": "http.response.body",
                        "body": body,
                        "more_body": False,
                    }
                )
            else:
                await send(state.start_with_diagnostic_headers)


class _ResponseState:
    def __init__(self) -> None:
        self.start_message: Message | None = None
        self.status: int | None = None
        self.headers: list[tuple[bytes, bytes]] = []
        self.has_body = False
        self.sent_start = False
        self.body_chunks: list[bytes] = []

    def capture_start(self, message: Message) -> None:
        self.start_message = message
        self.status = message["status"]
        self.headers = list(message.get("headers", []))

    @property
    def started(self) -> bool:
        return self.status is not None

    @property
    def is_error(self) -> bool:
        return self.status is not None and self.status >= 400

    @property
    def needs_empty_error_body(self) -> bool:
        return self.is_error and not self.has_body

    def should_replace_empty_error(self, message: Message, body: bytes) -> bool:
        return (
            self.needs_empty_error_body
            and not self.sent_start
            and not body
            and not message.get("more_body", False)
        )

    def should_buffer_empty_error_chunk(self, message: Message, body: bytes) -> bool:
        return (
            self.needs_empty_error_body
            and not self.sent_start
            and not body
            and message.get("more_body", False)
        )

    def should_add_content_length(self, message: Message, body: bytes) -> bool:
        return (
            not self._has_content_length
            and not self._is_event_stream
            and not message.get("more_body", False)
        )

    def should_buffer_body_for_content_length(self, message: Message) -> bool:
        return (
            not self.sent_start
            and self.start_message is not None
            and not self._has_content_length
            and not self._is_event_stream
            and message.get("more_body", False)
        )

    def should_flush_buffered_body(self, message: Message) -> bool:
        return (
            bool(self.body_chunks)
            and not self.sent_start
            and not message.get("more_body", False)
        )

    @property
    def start_with_diagnostic_headers(self) -> Message:
        if self._has_content_type:
            return self.start_message or {
                "type": "http.response.start",
                "status": self.status or 500,
                "headers": self.headers,
            }

        headers = list(self.headers)
        headers.append((b"content-type", self._fallback_content_type))
        return {
            "type": "http.response.start",
            "status": self.status or 500,
            "headers": headers,
        }

    @property
    def start_with_json_headers(self) -> Message:
        headers = [
            (name, value)
            for name, value in self.headers
            if name.lower() not in (b"content-type", b"content-length")
        ]
        headers.extend(
            [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(self.fallback_body)).encode()),
            ]
        )
        return {
            "type": "http.response.start",
            "status": self.status or 500,
            "headers": headers,
        }

    def start_with_content_length(self, body: bytes) -> Message:
        start = self.start_with_diagnostic_headers
        headers = [
            (name, value)
            for name, value in start.get("headers", [])
            if name.lower() != b"content-length"
        ]
        headers.append((b"content-length", str(len(body)).encode()))
        start["headers"] = headers
        return start

    @property
    def fallback_body(self) -> bytes:
        status = self.status or 500
        try:
            phrase = HTTPStatus(status).phrase.lower().replace(" ", "_")
        except ValueError:
            phrase = "http_error"
        return f'{{"error":"{phrase}"}}'.encode()

    @property
    def _has_content_type(self) -> bool:
        return any(name.lower() == b"content-type" for name, _ in self.headers)

    @property
    def _has_content_length(self) -> bool:
        return any(name.lower() == b"content-length" for name, _ in self.headers)

    @property
    def _is_event_stream(self) -> bool:
        return any(
            name.lower() == b"content-type" and b"text/event-stream" in value.lower()
            for name, value in self.headers
        )

    @property
    def _fallback_content_type(self) -> bytes:
        if self.is_error:
            return b"text/plain; charset=utf-8"
        return b"application/json"
