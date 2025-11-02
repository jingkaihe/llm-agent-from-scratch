from typing import Annotated, get_type_hints, get_origin, get_args
from inspect import Parameter, signature
from pydantic import create_model, Field
import aiofiles
from anthropic import AsyncAnthropic
import json, os, asyncio, yaml
from datetime import datetime
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def tool(f):
    def _process_parameter(name: str, param: Parameter, hints: dict) -> tuple:
        """Process a single parameter into a model field specification."""
        default = ... if param.default == Parameter.empty else param.default
        hint = hints.get(name, param.annotation)

        if get_origin(hint) == Annotated:
            base_type, *metadata = get_args(hint)
            description = next((m for m in metadata if isinstance(m, str)), None)
            return (
                base_type,
                Field(default=default, description=description)
                if description
                else default,
            )

        return (hint, default)

    hints = get_type_hints(f, include_extras=True)
    model_fields = {
        name: _process_parameter(name, param, hints)
        for name, param in signature(f).parameters.items()
    }

    m = create_model(f"{f.__name__} Input", **model_fields)
    m.run = lambda self: f(**self.model_dump())

    return {
        "name": f.__name__,
        "description": f.__doc__ or f"Tool: {f.__name__}",
        "model": m,
        "type": "local",
    }


class Toolbox:
    """Manages both local and MCP tools with proper async lifecycle management"""

    def __init__(self, local_tools=[], mcp_servers=[]):
        self.local_tools = local_tools
        self.mcp_servers = mcp_servers
        self.mcp_tools = []
        self.mcp_connections = []

    async def __aenter__(self):
        """Async context manager entry - connect to MCP servers"""
        if self.mcp_servers:
            await self._connect_mcp_servers()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - cleanup MCP connections"""
        await self.cleanup()
        return False

    async def _connect_mcp_servers(self):
        """Connect to all MCP servers and collect their tools"""
        for server_config in self.mcp_servers:
            # Expand cwd if it's a relative path or ~
            cwd = server_config.get("cwd")
            if cwd:
                cwd = str(Path(cwd).expanduser().resolve())

            for env_var in server_config.get("env", {}).keys():
                value = server_config["env"].get(env_var)
                if value is None:
                    value = os.environ.pop(env_var, None)
                if value is None:
                    value = input(f"Enter value for {env_var}: ")
                    value = value.strip()
                server_config["env"][env_var] = value

            server_params = StdioServerParameters(
                command=server_config["command"],
                args=server_config.get("args", []),
                env=server_config.get("env"),
                cwd=cwd,
            )

            # Create and enter context managers
            stdio_ctx = stdio_client(server_params)
            read, write = await stdio_ctx.__aenter__()

            session_ctx = ClientSession(read, write)
            session = await session_ctx.__aenter__()
            await session.initialize()

            # Store contexts for cleanup
            self.mcp_connections.append(
                {
                    "stdio_ctx": stdio_ctx,
                    "session_ctx": session_ctx,
                }
            )

            # Get tools from this server
            tools_list = await session.list_tools()

            for tool in tools_list.tools:
                self.mcp_tools.append(
                    {
                        "name": tool.name,
                        "description": tool.description or f"MCP Tool: {tool.name}",
                        "input_schema": tool.inputSchema,
                        "mcp_session": session,
                        "type": "mcp",
                    }
                )

    async def cleanup(self):
        """Properly cleanup all MCP connections"""
        for conn in reversed(self.mcp_connections):
            try:
                await conn["session_ctx"].__aexit__(None, None, None)
            except Exception as e:
                print(f"Error closing session: {e}")

            try:
                await conn["stdio_ctx"].__aexit__(None, None, None)
            except Exception as e:
                print(f"Error closing stdio: {e}")

    @property
    def all_tools(self):
        """Return all tools (local + MCP)"""
        return self.local_tools + self.mcp_tools

    def schema(self):
        return [
            {
                "name": t["name"],
                "description": t["description"],
                "input_schema": t.get("input_schema") or t["model"].model_json_schema(),
            }
            for t in self.all_tools
        ]

    async def run(self, name, input):
        tool = next(t for t in self.all_tools if t["name"] == name)

        if tool.get("type") == "mcp":
            result = await tool["mcp_session"].call_tool(name, input)
            return {
                "success": not result.isError,
                "output": "\n".join(
                    c.text for c in result.content if hasattr(c, "text")
                ),
            }
        else:
            return await tool["model"](**input).run()


@tool
async def read_file(filename: Annotated[str, "The path to the file to read"]):
    """Read the whole file"""
    async with aiofiles.open(filename, "r") as f:
        return {"success": True, "filename": filename, "output": await f.read()}


@tool
async def write_file(filename: str, content: str):
    """Write the file with the content. This is an overwrite"""
    async with aiofiles.open(filename, "w") as f:
        await f.write(content)
        return {"success": True, "filename": filename, "output": f"wrote to {filename}"}


@tool
async def edit_file(
    filename: str,
    old_text: Annotated[str, "the text to replace"],
    new_text: Annotated[str, "the text to replace with"],
):
    """Edit the file with the new text. Note that the text to replace should only appear once in the file."""
    async with aiofiles.open(filename, "r") as f:
        content = await f.read()

    if content.count(old_text) != 1:
        return {
            "success": False,
            "filename": filename,
            "output": f"old text appears {content.count(old_text)} times in the file",
        }

    async with aiofiles.open(filename, "w") as f:
        await f.write(content.replace(old_text, new_text))

    return {"success": True, "filename": filename, "output": f"edited {filename}"}


@tool
async def shell(
    command: Annotated[str, "command to execute"],
    timeout: Annotated[int, "timeout in seconds"] = 30,
):
    """Execute a bash command"""
    try:
        p = await asyncio.create_subprocess_shell(
            command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
        )
        stdout, _ = await asyncio.wait_for(p.communicate(), timeout)
        return {
            "success": p.returncode == 0,
            "command": command,
            "output": stdout.decode(),
        }
    except asyncio.TimeoutError:
        return {"success": False, "command": command, "output": "Timeout"}


async def loop(system_prompt, toolbox, messages, user_input):
    messages.append({"role": "user", "content": user_input})

    while True:
        msg = await client.messages.create(
            max_tokens=2048,
            thinking={"type": "enabled", "budget_tokens": 1024},
            system=[{"type": "text", "text": system_prompt}],
            messages=messages,
            model="claude-sonnet-4-5",
            tools=toolbox.schema(),
        )

        messages.append({"role": "assistant", "content": msg.content})

        thinking_text = " ".join(
            t.thinking for t in msg.content if t.type == "thinking"
        )
        if thinking_text:
            print(f"💭 {thinking_text}")

        agent_text = " ".join(t.text for t in msg.content if t.type == "text")
        if agent_text:
            print(f"🤖 {agent_text}")

        tools = [t for t in msg.content if t.type == "tool_use"]
        if not tools:
            break

        # Execute all tools and collect results
        results = await asyncio.gather(*[toolbox.run(t.name, t.input) for t in tools])

        # Display results and send back to model
        for t, r in zip(tools, results):
            status = "✅" if r.get("success") else "❌"
            print(f"{status} {t.name}:")
            print(json.dumps(r, indent=2))

        messages.append(
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": t.id,
                        "content": json.dumps(r),
                    }
                    for t, r in zip(tools, results)
                ],
            }
        )


client = AsyncAnthropic()


def load_mcp_config(config_path="mcp.yaml"):
    """Load MCP server configuration from YAML file"""
    config_file = Path(config_path)

    if not config_file.exists():
        return []

    try:
        with open(config_file, "r") as f:
            config = yaml.safe_load(f)
            return config.get("servers", [])
    except Exception as e:
        print(f"⚠️  Error loading MCP config from {config_path}: {e}")
        return []


async def run_agent(tools=[], mcp_servers=[]):
    """Run the agent with local tools and optional MCP servers"""
    async with Toolbox(local_tools=tools, mcp_servers=mcp_servers) as toolbox:
        messages = []
        system_prompt = f"""Your name is HAL.
You are an interactive CLI tool that helps with software engineering and production operations tasks.
You are running on {str(os.uname())}, today is {datetime.now().strftime("%Y-%m-%d")}
"""

        if toolbox.mcp_tools:
            print(
                f"🔌 Connected to {len(mcp_servers)} MCP server(s) with {len(toolbox.mcp_tools)} tool(s)"
            )

        print("enter 'exit' to quit")

        try:
            while True:
                user_input = input("> ")
                if user_input.lower() == "exit":
                    print("👋 Goodbye!")
                    break
                await loop(system_prompt, toolbox, messages, user_input)
        except (KeyboardInterrupt, EOFError):
            print("👋 Goodbye!")


if __name__ == "__main__":
    # Load MCP servers from mcp.yaml if it exists, otherwise use default config
    mcp_servers = load_mcp_config("mcp.yaml")

    asyncio.run(
        run_agent(
            tools=[read_file, write_file, edit_file, shell], mcp_servers=mcp_servers
        )
    )
