"""A real MCP server on loopback, for connector tests.

Built on the MCP SDK's own server over Streamable HTTP and run by uvicorn in a
thread, so the client under test speaks the actual protocol rather than a mock
of it. Knobs a test turns:

- ``token``: the bearer (or ``header``/``value`` pair) every request must carry;
  anything else is 401.
- ``add``/``remove`` tools at runtime, to change what ``tools/list`` says.
- ``fail_with``: answer every request with this status (500, 401, 403 …).
- ``hang_calls``: tool calls never return (a server that died mid-call).
- ``/redirect``: a 307 to wherever ``redirect_to`` points.

It also serves a minimal OAuth 2.1 authorization server (RFC 9728 resource
metadata, RFC 8414 server metadata, RFC 7591 registration, PKCE S256) for the
OAuth tests; ``oauth=True`` makes the MCP endpoint demand its access tokens.
"""

from __future__ import annotations

import base64
import contextlib
import hashlib
import secrets
import socket
import threading
import time
from collections.abc import Callable
from typing import Any

import mcp_types as types
import uvicorn
from mcp.server.mcpserver import MCPServer
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse, Response
from starlette.routing import Mount, Route


def _free_port() -> int:
    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    return port


class FakeMCP:
    def __init__(self, *, token: str | None = "s3cret", header: str = "Authorization", oauth: bool = False) -> None:
        self.token = token
        self.header = header
        self.oauth = oauth
        self.fail_with: int | None = None
        self.hang_calls = False
        self.redirect_to = "http://127.0.0.1:9/mcp"
        self.requests = 0
        self.calls: list[tuple[str, dict[str, Any]]] = []
        # OAuth state
        self.clients: dict[str, dict[str, Any]] = {}
        self.codes: dict[str, dict[str, Any]] = {}
        self.access_tokens: set[str] = set()
        self.refresh_tokens: dict[str, str] = {}
        self.token_requests = 0
        self.refresh_requests = 0
        self.token_delay = 0.0
        self.server = MCPServer("fake")
        self._install_defaults()
        self.port = _free_port()
        self.base = f"http://127.0.0.1:{self.port}"
        self.url = f"{self.base}/mcp"
        self._uvicorn: uvicorn.Server | None = None

    # -- tools ------------------------------------------------------------

    def _install_defaults(self) -> None:
        fake = self

        @self.server.tool(
            description="Doanh thu năm gần nhất của một mã, từ sổ tay của người dùng.",
            annotations=types.ToolAnnotations(read_only_hint=True),
        )
        def get_revenue(ticker: str) -> str:
            fake.calls.append(("get_revenue", {"ticker": ticker}))
            if fake.hang_calls:
                time.sleep(30)
            return f"{ticker}: doanh thu 2025 là 61.782 tỷ đồng"

        @self.server.tool(description="Ghi một ghi chú vào sổ tay.")
        def save_note(text: str) -> str:
            fake.calls.append(("save_note", {"text": text}))
            return "đã lưu"

        @self.server.tool(
            description="Xoá sổ tay.",
            annotations=types.ToolAnnotations(read_only_hint=True, destructive_hint=True),
        )
        def wipe_notes() -> str:
            fake.calls.append(("wipe_notes", {}))
            return "đã xoá"

    def add(self, fn: Callable[..., Any], *, description: str, read_only: bool | None = True) -> None:
        annotations = types.ToolAnnotations(read_only_hint=read_only) if read_only is not None else None
        self.server.add_tool(fn, description=description, annotations=annotations)

    def remove(self, name: str) -> None:
        self.server.remove_tool(name)

    def redescribe(self, name: str, description: str) -> None:
        tool = self.server._tool_manager.get_tool(name)  # noqa: SLF001 - test double
        tool.description = description

    # -- http -------------------------------------------------------------

    def _authorised(self, request: Request) -> bool:
        if self.oauth:
            value = request.headers.get("authorization", "")
            return value.startswith("Bearer ") and value[7:] in self.access_tokens
        if self.token is None:
            return True
        expected = f"Bearer {self.token}" if self.header.lower() == "authorization" else self.token
        return request.headers.get(self.header) == expected

    def app(self) -> Starlette:
        mcp_app = self.server.streamable_http_app(stateless_http=True, json_response=True)
        fake = self

        async def guarded(scope, receive, send):
            if scope["type"] == "http":
                request = Request(scope, receive)
                fake.requests += 1
                if fake.fail_with is not None:
                    await Response(status_code=fake.fail_with)(scope, receive, send)
                    return
                if not fake._authorised(request):
                    headers = {}
                    if fake.oauth:
                        headers["WWW-Authenticate"] = (
                            f'Bearer resource_metadata="{fake.base}/.well-known/oauth-protected-resource"'
                        )
                    await JSONResponse({"error": "unauthorized"}, status_code=401, headers=headers)(scope, receive, send)
                    return
            await mcp_app(scope, receive, send)

        async def redirect(request: Request) -> Response:
            return RedirectResponse(fake.redirect_to, status_code=307)

        async def resource_metadata(request: Request) -> Response:
            return JSONResponse({"resource": fake.url, "authorization_servers": [fake.base]})

        async def server_metadata(request: Request) -> Response:
            return JSONResponse(
                {
                    "issuer": fake.base,
                    "authorization_endpoint": f"{fake.base}/authorize",
                    "token_endpoint": f"{fake.base}/token",
                    "registration_endpoint": f"{fake.base}/register",
                    "code_challenge_methods_supported": ["S256"],
                    "response_types_supported": ["code"],
                    "grant_types_supported": ["authorization_code", "refresh_token"],
                }
            )

        async def register(request: Request) -> Response:
            body = await request.json()
            client_id = secrets.token_hex(8)
            fake.clients[client_id] = body
            return JSONResponse({"client_id": client_id, **body}, status_code=201)

        async def authorize(request: Request) -> Response:
            params = request.query_params
            code = secrets.token_hex(8)
            fake.codes[code] = {
                "client_id": params["client_id"],
                "challenge": params["code_challenge"],
                "redirect_uri": params["redirect_uri"],
            }
            return RedirectResponse(f"{params['redirect_uri']}?code={code}&state={params['state']}", status_code=302)

        async def token(request: Request) -> Response:
            form = await request.form()
            fake.token_requests += 1
            if fake.token_delay:
                import asyncio

                await asyncio.sleep(fake.token_delay)
            if form.get("grant_type") == "authorization_code":
                grant = fake.codes.pop(str(form.get("code")), None)
                verifier = str(form.get("code_verifier") or "")
                challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
                if grant is None or grant["challenge"] != challenge or grant["redirect_uri"] != form.get("redirect_uri"):
                    return JSONResponse({"error": "invalid_grant"}, status_code=400)
            elif form.get("grant_type") == "refresh_token":
                fake.refresh_requests += 1
                old = str(form.get("refresh_token"))
                if old not in fake.refresh_tokens:
                    return JSONResponse({"error": "invalid_grant"}, status_code=400)
                # Rotating refresh tokens: the old one is spent.
                fake.access_tokens.discard(fake.refresh_tokens.pop(old))
            else:
                return JSONResponse({"error": "unsupported_grant_type"}, status_code=400)
            access, refresh = secrets.token_hex(12), secrets.token_hex(12)
            fake.access_tokens.add(access)
            fake.refresh_tokens[refresh] = access
            return JSONResponse(
                {"access_token": access, "refresh_token": refresh, "token_type": "Bearer", "expires_in": 3600}
            )

        @contextlib.asynccontextmanager
        async def lifespan(app):
            async with mcp_app.router.lifespan_context(app):
                yield

        return Starlette(
            routes=[
                Route("/redirect", redirect, methods=["GET", "POST"]),
                Route("/.well-known/oauth-protected-resource", resource_metadata),
                Route("/.well-known/oauth-protected-resource/mcp", resource_metadata),
                Route("/.well-known/oauth-authorization-server", server_metadata),
                Route("/register", register, methods=["POST"]),
                Route("/authorize", authorize),
                Route("/token", token, methods=["POST"]),
                Mount("/", app=guarded),
            ],
            lifespan=lifespan,
        )

    def start(self) -> "FakeMCP":
        config = uvicorn.Config(self.app(), host="127.0.0.1", port=self.port, log_level="warning", lifespan="on")
        self._uvicorn = uvicorn.Server(config)
        threading.Thread(target=self._uvicorn.run, daemon=True).start()
        deadline = time.monotonic() + 10
        while not self._uvicorn.started:
            if time.monotonic() > deadline:
                raise RuntimeError("fake MCP server did not start")
            time.sleep(0.05)
        return self

    def stop(self) -> None:
        if self._uvicorn is not None:
            self._uvicorn.should_exit = True
            time.sleep(0.2)


__all__ = ["FakeMCP"]
