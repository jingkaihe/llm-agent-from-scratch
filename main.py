from typing import Annotated, get_type_hints, get_origin, get_args
from inspect import Parameter, signature
from pydantic import create_model, Field
import aiofiles
from anthropic import AsyncAnthropic
import json, os, asyncio
from datetime import datetime


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
    }


class Toolbox:
    def __init__(self, tools):
        self.tools = tools

    def schema(self):
        return [
            {
                "name": t["name"],
                "description": t["description"],
                "input_schema": t["model"].model_json_schema(),
            }
            for t in self.tools
        ]

    async def run(self, name, input):
        tool = next(t for t in self.tools if t["name"] == name)
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


async def run_agent(tools=[]):
    toolbox = Toolbox(tools)
    messages = []
    system_prompt = f"""Your name is HAL.
You are an interactive CLI tool that helps with software engineering and production operations tasks.
You are running on {str(os.uname())}, today is {datetime.now().strftime("%Y-%m-%d")}
"""
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


asyncio.run(run_agent(tools=[read_file, write_file, edit_file, shell]))
