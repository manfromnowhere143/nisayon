import asyncio
import json
import sys

from mcp import Client
from mcp.client.stdio import StdioServerParameters


def test_real_stdio_protocol_and_shared_memory(workspace):
    async def exercise():
        params = StdioServerParameters(
            command=sys.executable, args=["-m", "nisayon.mcp_server"], cwd=workspace
        )
        async with Client(params) as client:
            tools = {tool.name: tool for tool in (await client.list_tools()).tools}
            assert len(tools) == 11
            assert tools["project_context"].annotations.read_only_hint is True
            result = await client.call_tool("project_context")
            assert not result.is_error
            assert result.structured_content["project"] == "Nisayon"
            note = await client.call_tool(
                "memory_add",
                {
                    "title": "Reset semantics",
                    "body": "Needs a measured bound",
                    "sources": ["docs/ARCHITECTURE.md"],
                },
            )
            assert not note.is_error
            note_id = note.structured_content["id"]
            assert (workspace / "memory/notes" / f"{note_id}.json").is_file()
            found = await client.call_tool("memory_search", {"query": "reset"})
            assert note_id in json.dumps(found.model_dump())
            checkpoint = await client.call_tool(
                "checkpoint_save", {"summary": "Context verified", "next_action": "Qualify backend"}
            )
            assert not checkpoint.is_error
            resource = await client.read_resource("nisayon://context")
            assert "Qualify backend" in resource.contents[0].text
            denied = await client.call_tool("project_read", {"path": "../secret"})
            assert denied.is_error
            resources = await client.list_resources()
            assert {str(row.uri) for row in resources.resources} == {
                "nisayon://context",
                "nisayon://architecture",
            }

    asyncio.run(exercise())
