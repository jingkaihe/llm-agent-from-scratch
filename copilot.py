import json, asyncio
import click
from hacks.openai_client import create_openai_copilot_client
from main import read_file, write_file, edit_file, shell, load_mcp_config


async def loop(system_prompt, toolbox, messages, user_input, model="claude-sonnet-4.5"):
    messages.append({"role": "user", "content": user_input})

    while True:
        # Convert Anthropic tool schema to OpenAI function format
        tools = (
            [
                {
                    "type": "function",
                    "function": {
                        "name": t["name"],
                        "description": t["description"],
                        "parameters": t["input_schema"],
                    },
                }
                for t in toolbox.schema()
            ]
            if toolbox.schema()
            else None
        )

        completion = await client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system_prompt}] + messages,
            tools=tools,
            tool_choice="auto" if tools else None,
        )

        msg = completion.choices[0].message
        messages.append(
            {"role": "assistant", "content": msg.content, "tool_calls": msg.tool_calls}
        )

        if msg.content:
            print(f"🤖 {msg.content}")

        if not msg.tool_calls:
            break

        for tool_call in msg.tool_calls:
            tool_name = tool_call.function.name
            tool_args = json.loads(tool_call.function.arguments)
            result = await toolbox.run(tool_name, tool_args)

            status = "✅" if result.get("success") else "❌"
            print(f"{status} {tool_name}:")
            print(json.dumps(result, indent=2))

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result),
                }
            )


client = create_openai_copilot_client()


@click.command()
@click.option(
    "--model",
    type=click.Choice(
        ["gpt-5", "gpt-4.1", "claude-sonnet-4.5", "gemini-2.5-pro"],
        case_sensitive=False,
    ),
    default="claude-sonnet-4.5",
    help="The model to use for the agent",
)
def main(model):
    """Run the copilot agent with the specified model"""
    from main import run_agent

    print(f"using {model}")

    # Create a wrapped loop that includes the model
    async def model_loop(system_prompt, toolbox, messages, user_input):
        return await loop(system_prompt, toolbox, messages, user_input, model=model)

    mcp_servers = load_mcp_config("mcp.yaml")
    asyncio.run(
        run_agent(
            tools=[read_file, write_file, edit_file, shell],
            mcp_servers=mcp_servers,
            loop=model_loop,
        )
    )


if __name__ == "__main__":
    main()
