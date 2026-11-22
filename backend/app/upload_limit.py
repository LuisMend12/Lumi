"""Refuse oversized photo uploads before the body is read (#58).

FastAPI parses a multipart body before it resolves dependencies, so without
this an unauthenticated client could make the server read and spool a huge
upload before `require_user` answers 401. This ASGI middleware checks the
declared Content-Length first and answers without touching the body:

- more than the limit -> 413
- no Content-Length on an upload path -> 411 (browsers always send one for a form upload)
"""

import json

from starlette.types import ASGIApp, Receive, Scope, Send

# Room for the multipart boundaries and the lat/lon fields around a full-size photo.
FORM_OVERHEAD_BYTES = 64 * 1024


class UploadSizeLimit:
    def __init__(self, app: ASGIApp, *, paths: set[str], max_body_bytes: int, limit_label: str) -> None:
        self.app = app
        self.paths = paths
        self.max_body_bytes = max_body_bytes
        self.limit_label = limit_label

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] != "POST" or scope["path"] not in self.paths:
            await self.app(scope, receive, send)
            return
        declared = dict(scope["headers"]).get(b"content-length")
        if declared is None:
            await _reply(send, 411, "Send the photo as a normal form upload (Content-Length is required).")
            return
        try:
            size = int(declared)
        except ValueError:
            await _reply(send, 400, "Invalid Content-Length header.")
            return
        if size > self.max_body_bytes:
            await _reply(send, 413, f"The photo is larger than {self.limit_label}. Send a smaller one.")
            return
        await self.app(scope, receive, send)


async def _reply(send: Send, status: int, detail: str) -> None:
    body = json.dumps({"detail": detail}).encode()
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())],
        }
    )
    await send({"type": "http.response.body", "body": body})
