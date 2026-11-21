#!/usr/bin/env python3
# SiYuan - https://github.com/siyuan-note/siyuan
# Copyright (c) 2020-present, b3log.org
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Minimal MCP smoke test for the SiYuan connector endpoint.

It performs the same handshake WorkBuddy performs when a user connects the
connector -- ``initialize`` -> ``notifications/initialized`` -> ``tools/list`` --
using nothing but the Python standard library, so it can be pasted into an
issue report without installing anything.

Usage:
    SIYUAN_API_TOKEN=xxxx python3 scripts/smoke_test.py
    python3 scripts/smoke_test.py --url https://siyuan.example.com --token xxxx
    python3 scripts/smoke_test.py --insecure     # self-signed certificate

Exit code 0 means the endpoint spoke MCP and returned a tool list; anything
else is a connectivity, certificate or token problem.
"""

from __future__ import annotations

import argparse
import http.client
import json
import os
import ssl
import sys
import urllib.parse

# The kernel negotiates this down to the version it implements and reports the
# agreed value back in the initialize result.
PROTOCOL_VERSION = "2026-07-28"
CLIENT_INFO = {"name": "siyuan-workbuddy-connector-smoke-test", "version": "1.0.0"}


class SmokeError(RuntimeError):
    pass


def request(
    conn: http.client.HTTPConnection,
    method: str,
    path: str,
    payload: dict | None,
    token: str,
    session_id: str | None = None,
) -> tuple[int, dict[str, str], bytes]:
    headers = {
        "Authorization": f"Token {token}",
        "Accept": "application/json, text/event-stream",
    }
    body = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if session_id:
        headers["Mcp-Session-Id"] = session_id

    conn.request(method, path, body=body, headers=headers)
    response = conn.getresponse()
    response_headers = {k.lower(): v for k, v in response.getheaders()}
    if "text/event-stream" in response_headers.get("content-type", ""):
        # Read exactly one SSE event: the server keeps the stream open, so a
        # plain read() would block until the timeout expires.
        chunks: list[bytes] = []
        while True:
            line = response.readline()
            if not line:
                break
            chunks.append(line)
            if line in (b"\n", b"\r\n") and any(chunk.startswith(b"data:") for chunk in chunks):
                break
        raw = b"".join(chunks)
    else:
        raw = response.read()
    return response.status, response_headers, raw


def read_json_rpc(conn: http.client.HTTPConnection, raw: bytes, headers: dict[str, str]) -> dict:
    """Decode a JSON-RPC message from either a plain body or an SSE stream."""
    content_type = headers.get("content-type", "")
    if "text/event-stream" not in content_type:
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as err:
            raise SmokeError(f"response is not JSON: {raw[:200]!r} ({err})") from err

    data_lines: list[str] = []
    for line in raw.decode("utf-8", "replace").splitlines():
        if line.startswith("data:"):
            data_lines.append(line[5:].strip())
        elif not line.strip() and data_lines:
            break  # end of the first SSE event
    if not data_lines:
        raise SmokeError(f"empty SSE stream: {raw[:200]!r}")
    return json.loads("\n".join(data_lines))


def check(url: str, token: str, insecure: bool, timeout: float) -> None:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in ("http", "https"):
        raise SmokeError(f"unsupported scheme {parsed.scheme!r}; use http or https")
    path = parsed.path or "/mcp"
    if not path.endswith("/mcp"):
        path = path.rstrip("/") + "/mcp"

    context = None
    if parsed.scheme == "https":
        context = ssl.create_default_context()
        if insecure:
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
        conn: http.client.HTTPConnection = http.client.HTTPSConnection(
            parsed.hostname, parsed.port or 443, timeout=timeout, context=context
        )
    else:
        conn = http.client.HTTPConnection(parsed.hostname, parsed.port or 80, timeout=timeout)

    print(f"endpoint {parsed.scheme}://{parsed.netloc}{path}")
    try:
        status, headers, raw = request(
            conn,
            "POST",
            path,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": CLIENT_INFO,
                },
            },
            token,
        )
        if status == 401:
            raise SmokeError("401 Unauthorized -- check the API token in SiYuan Settings -> Authentication")
        if status == 403:
            raise SmokeError("403 Forbidden -- the token is not an administrator token")
        if status >= 400:
            raise SmokeError(f"initialize failed: HTTP {status} {raw[:200]!r}")

        message = read_json_rpc(conn, raw, headers)
        if "error" in message:
            raise SmokeError(f"initialize rejected: {message['error']}")
        result = message.get("result", {})
        server = result.get("serverInfo", {})
        print(f"server   {server.get('name')} {server.get('version')} (MCP {result.get('protocolVersion')})")

        session_id = headers.get("mcp-session-id")
        if session_id:
            print(f"session  {session_id}")

        request(
            conn,
            "POST",
            path,
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            token,
            session_id,
        )

        status, headers, raw = request(
            conn, "POST", path, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, token, session_id
        )
        if status >= 400:
            raise SmokeError(f"tools/list failed: HTTP {status} {raw[:200]!r}")
        listed = read_json_rpc(conn, raw, headers).get("result", {}).get("tools", [])
        if not listed:
            raise SmokeError("the server returned no tools; check the workspace capability settings")
        names = sorted(tool.get("name", "?") for tool in listed)
        print(f"tools    {len(names)} available")
        print("         " + ", ".join(names[:12]) + (" ..." if len(names) > 12 else ""))
        print("OK")
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001 - closing a broken socket must not mask the real error
            pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test the SiYuan MCP endpoint used by the connector.")
    parser.add_argument(
        "--url",
        default=os.environ.get("SIYUAN_URL", "http://127.0.0.1:6806"),
        help="kernel base URL or full /mcp URL (default: %(default)s)",
    )
    parser.add_argument("--token", default=os.environ.get("SIYUAN_API_TOKEN", ""), help="API token (or SIYUAN_API_TOKEN)")
    parser.add_argument("--insecure", action="store_true", help="skip TLS certificate verification")
    parser.add_argument("--timeout", type=float, default=15.0, help="per-request timeout in seconds")
    args = parser.parse_args()

    if not args.token:
        parser.error("an API token is required: pass --token or set SIYUAN_API_TOKEN")

    try:
        check(args.url, args.token, args.insecure, args.timeout)
    except (SmokeError, OSError, http.client.HTTPException, json.JSONDecodeError) as err:
        print(f"FAILED {err}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
