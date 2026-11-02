"""Native local MCP transport; effect journal is independent of client receipts."""

import asyncio
import hashlib
import importlib.metadata
import inspect
import json
import os
import platform
import socket
import sys
from pathlib import Path

import uvicorn
from agents import set_tracing_disabled
from agents.mcp import MCPServerStreamableHttp
from mcp.server import Server
from mcp.types import CallToolResult, ListToolsResult, TextContent, Tool, ToolAnnotations

set_tracing_disabled(True)


def source_identity():
    source = Path(inspect.getfile(MCPServerStreamableHttp))
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    if digest != "f2596229ed74af0c879e966c695f8095813d6e53ee083db22be551f8d8c0506b":
        raise ValueError("Agents SDK server.py differs from the qualified main revision")
    if importlib.metadata.version("mcp") != "2.3.0":
        raise ValueError("This experiment requires MCP 2.3.0")
    return {
        "agents_source_commit": "e355d69152d4f4730dfb03b63dbce53e8d9f5d8c",
        "server_sha256": digest,
    }


def append(path, event):
    with path.open("a") as stream:
        stream.write(json.dumps(event, sort_keys=True) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


class OneFault:
    """ASGI proxy returns one 503 before execution or after collecting its response."""

    def __init__(self, app, phase, requests):
        self.app, self.phase, self.requests = app, phase, requests
        self.calls = 0

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] != "POST":
            return await self.app(scope, receive, send)
        chunks = []
        while True:
            chunk = await receive()
            chunks.append(chunk)
            if not chunk.get("more_body", False):
                break
        body = b"".join(chunk.get("body", b"") for chunk in chunks)
        message = json.loads(body)
        is_call = message.get("method") == "tools/call"
        if is_call:
            self.calls += 1
            append(
                self.requests,
                {
                    "attempt": self.calls,
                    "request_id": message.get("id"),
                    "arguments": message["params"].get("arguments"),
                },
            )
        inject = is_call and self.calls == 1 and self.phase != "none"

        async def fail():
            await send(
                {
                    "type": "http.response.start",
                    "status": 503,
                    "headers": [(b"content-type", b"text/plain")],
                }
            )
            await send({"type": "http.response.body", "body": b"Controlled response failure"})

        if inject and self.phase == "before":
            return await fail()
        pending = list(chunks)

        async def replay_receive():
            return pending.pop(0) if pending else await receive()

        captured = []

        async def capture(message):
            captured.append(message)

        if inject:
            await self.app(scope, replay_receive, capture)
            assert any(m["type"] == "http.response.start" and m["status"] == 200 for m in captured)
            return await fail()
        return await self.app(scope, replay_receive, send)


async def run_case(folder, phase, retries, deduplicate=False, serialized=True):
    folder.mkdir(parents=True, exist_ok=False)
    effects, requests = folder / "effects.jsonl", folder / "requests.jsonl"
    effects.touch()
    requests.touch()
    known = {}
    count = 0

    async def list_tools(_context, _params):
        return ListToolsResult(
            tools=[
                Tool(
                    name="commit_effect",
                    inputSchema={
                        "type": "object",
                        "properties": {"operation_key": {"type": "string"}},
                        "required": ["operation_key"],
                    },
                    annotations=ToolAnnotations(
                        readOnlyHint=False, destructiveHint=True, idempotentHint=False
                    ),
                )
            ]
        )

    async def call_tool(_context, params):
        nonlocal count
        assert params.name == "commit_effect"
        key = params.arguments["operation_key"]
        if deduplicate and key in known:
            return known[key]
        count += 1
        append(effects, {"effect_number": count, "operation_key": key})
        result = CallToolResult(content=[TextContent(type="text", text=str(count))])
        known[key] = result
        return result

    app = Server("nisayon-local-effect-probe", on_list_tools=list_tools, on_call_tool=call_tool)
    proxy = OneFault(
        app.streamable_http_app(json_response=True, stateless_http=True), phase, requests
    )
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    sock.listen()
    server = uvicorn.Server(uvicorn.Config(proxy, log_level="error", lifespan="on", ws="none"))
    task = asyncio.create_task(server.serve(sockets=[sock]))

    async def ready():
        while not server.started:
            if task.done():
                await task
            await asyncio.sleep(0.01)

    observed = {
        "phase": phase,
        "retry_budget": retries,
        "deduplicate": deduplicate,
        "serialized": serialized,
        "status": "unresolved",
    }
    try:
        await asyncio.wait_for(ready(), timeout=5)
        async with MCPServerStreamableHttp(
            params={"url": f"http://127.0.0.1:{sock.getsockname()[1]}/mcp"},
            max_retry_attempts=retries,
            retry_backoff_seconds_base=0,
            client_session_timeout_seconds=2,
        ) as client:
            client._serialize_session_requests = serialized
            tools = await client.list_tools()
            assert tools[0].annotations.idempotent_hint is False
            observed["protocol"] = client.session.protocol_version
            try:
                result = await asyncio.wait_for(
                    client.call_tool("commit_effect", {"operation_key": "one-intent"}), timeout=10
                )
                observed.update(
                    status="error_result" if result.is_error else "acknowledged",
                    result_text=[item.text for item in result.content if item.type == "text"],
                )
            except Exception as exc:
                observed.update(status="exception", exception_type=type(exc).__name__)
    finally:
        server.should_exit = True
        await asyncio.wait_for(task, timeout=5)
        sock.close()
    # Read only persisted server events; client outputs never supply the outcome count.
    observed["requests"] = len(requests.read_text().splitlines())
    observed["effects"] = len(effects.read_text().splitlines())
    observed["journal_sha256"] = hashlib.sha256(effects.read_bytes()).hexdigest()
    (folder / "observation.json").write_text(json.dumps(observed, indent=2) + "\n")
    return observed


async def main(destination):
    identity = source_identity()
    destination.mkdir(parents=True, exist_ok=False)
    rows = []
    for serialized in (True, False):
        for phase in ("none", "before", "after"):
            for retries in (0, 1):
                rows.append(
                    await run_case(
                        destination / f"{serialized}-{phase}-{retries}",
                        phase,
                        retries,
                        serialized=serialized,
                    )
                )
        rows.append(
            await run_case(
                destination / f"{serialized}-deduplicated",
                "after",
                1,
                deduplicate=True,
                serialized=serialized,
            )
        )
    output = {
        "source": identity,
        "python": sys.version,
        "platform": platform.platform(),
        "versions": {
            p: importlib.metadata.version(p)
            for p in ("openai-agents", "mcp", "mcp-types", "uvicorn", "httpx2")
        },
        "rows": rows,
    }
    (destination / "results.json").write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps(output, indent=2))
    expected = {
        ("none", 0): ("acknowledged", 1, 1),
        ("none", 1): ("acknowledged", 1, 1),
        ("before", 0): ("exception", 1, 0),
        ("before", 1): ("acknowledged", 2, 1),
        ("after", 0): ("exception", 1, 1),
        ("after", 1): ("acknowledged", 2, 2),
    }
    for row in rows:
        oracle = (
            ("acknowledged", 2, 1)
            if row["deduplicate"]
            else expected[row["phase"], row["retry_budget"]]
        )
        assert (row["status"], row["requests"], row["effects"]) == oracle, row


if __name__ == "__main__":
    asyncio.run(main(Path(sys.argv[1])))
