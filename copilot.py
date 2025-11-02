import json, asyncio
import click
from hacks.openai_client import create_openai_copilot_client
from main import read_file, write_file, edit_file, shell, load_mcp_config


async def loop_responses(system_prompt, toolbox, messages, user_input, model="gpt-5"):
    """Loop using OpenAI Responses API - for gpt-5 and gpt-5-codex"""
    # Note: messages maintains the full conversation history as input items
    # Add new user input to the conversation
    messages.append({"role": "user", "content": user_input})

    while True:
        # Convert Anthropic tool schema to OpenAI Responses API format
        tools = (
            [
                {
                    "type": "function",
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t["input_schema"],
                }
                for t in toolbox.schema()
            ]
            if toolbox.schema()
            else None
        )

        response = await client.responses.create(
            model=model,
            instructions=system_prompt,
            input=messages,
            tools=tools,
            tool_choice="auto" if tools else None,
        )

        # Add response output to conversation history
        messages.extend(response.output)

        # Extract and display reasoning and text messages
        for item in response.output:
            if item.type == "reasoning":
                # Display reasoning content if available, otherwise show summary
                if item.content:
                    reasoning_text = " ".join(
                        c.text for c in item.content if c.type == "reasoning_text"
                    )
                    if reasoning_text:
                        print(f"💭 {reasoning_text}")
                elif item.summary:
                    summary_text = " ".join(
                        s.text for s in item.summary if s.type == "summary_text"
                    )
                    if summary_text:
                        print(f"💭 {summary_text}")
            elif item.type == "message" and item.role == "assistant":
                for content in item.content:
                    if content.type == "output_text":
                        print(f"🤖 {content.text}")

        # Extract function calls
        function_calls = [
            item for item in response.output if item.type == "function_call"
        ]

        if not function_calls:
            break

        # Execute all tools and collect results
        results = await asyncio.gather(
            *[
                toolbox.run(item.name, json.loads(item.arguments))
                for item in function_calls
            ]
        )

        # Display results and add function outputs to conversation history
        for item, result in zip(function_calls, results):
            status = "✅" if result.get("success") else "❌"
            print(f"{status} {item.name}:")
            print(json.dumps(result, indent=2))

            messages.append(
                {
                    "type": "function_call_output",
                    "call_id": item.call_id,
                    "output": json.dumps(result),
                }
            )


async def loop_completions(
    system_prompt, toolbox, messages, user_input, model="claude-sonnet-4.5"
):
    """Loop using OpenAI Chat Completions API - for all other models"""
    messages.append({"role": "user", "content": user_input})

    while True:
        # Convert Anthropic tool schema to OpenAI Chat Completions format
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

        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system_prompt}] + messages,
            tools=tools,
            tool_choice="auto" if tools else None,
        )

        msg = response.choices[0].message
        messages.append(
            {"role": "assistant", "content": msg.content, "tool_calls": msg.tool_calls}
        )

        if msg.content:
            print(f"🤖 {msg.content}")

        tool_calls = msg.tool_calls
        if not tool_calls:
            break

        # Execute all tools and collect results
        results = await asyncio.gather(
            *[
                toolbox.run(tc.function.name, json.loads(tc.function.arguments))
                for tc in tool_calls
            ]
        )

        # Display results and add to messages
        for tc, result in zip(tool_calls, results):
            status = "✅" if result.get("success") else "❌"
            print(f"{status} {tc.function.name}:")
            print(json.dumps(result, indent=2))

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result),
                }
            )


client = create_openai_copilot_client()


@click.command()
@click.option(
    "--model",
    type=click.Choice(
        [
            "gpt-5",
            "gpt-5-codex",
            "gpt-4.1",
            "claude-sonnet-4.5",
            "gemini-2.5-pro",
            "grok-code-fast-1",
        ],
        case_sensitive=False,
    ),
    default="claude-sonnet-4.5",
    help="The model to use for the agent",
)
def main(model):
    """Run the copilot agent with the specified model"""
    from main import run_agent

    print(f"Using {model}")

    # Select the appropriate loop based on model
    if model in ["gpt-5", "gpt-5-codex"]:
        print("Using Responses API")
        loop_func = loop_responses
    else:
        print("Using Chat Completions API")
        loop_func = loop_completions

    # Create a wrapped loop that includes the model
    async def model_loop(system_prompt, toolbox, messages, user_input):
        return await loop_func(
            system_prompt, toolbox, messages, user_input, model=model
        )

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
