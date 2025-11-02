# LLM Agent From Scratch

A project for building LLM agents using Python, Pydantic, and Anthropic's API.

## Prerequisites
- `uv` package manager

## Setup Instructions

### 1. Install uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh

# If you are on macOS
brew install uv
```

### 2. Install Python (if needed)

If you don't have Python installed, uv can install it for you:

```bash
uv python install
```

### 3. Initialize the Project

Clone the repository and navigate to the project directory, then sync the dependencies:

```bash
uv sync
```

This will:
- Create a virtual environment at `.venv`
- Install all project dependencies from `pyproject.toml`
- Lock the dependencies in `uv.lock`

## Dependencies

- **pydantic**: Data validation using Python type annotations
- **anthropic**: Official Python SDK for Anthropic's Claude API
- **jupyter**: Interactive notebook environment
- **pyyaml**: YAML parser for configuration files
- **mcp**: Model Context Protocol for extensible tool integrations

## Usage

### Basic Usage

To run the full example:
```bash
uv run main.py
```

To open the main notebook:
```bash
uv run jupyter notebook llm-agent-from-scratch.ipynb
```

**Note:** You can also manually activate the virtual environment with `source .venv/bin/activate` if preferred, but it's not required when using `uv run`.

### MCP Server Configuration

The agent supports extending functionality through Model Context Protocol (MCP) servers. You can configure MCP servers using a `mcp.yaml` file in the project directory.

#### Configuration Format

Create a `mcp.yaml` file in the project root with the following structure:

```yaml
servers:
  server_name:
    command: command_to_run
    args:
      - "arg1"
      - "arg2"
    env:
      ENV_VAR: value
```

Each server is identified by a unique name (e.g., `github`, `filesystem`) and tools from that server will be prefixed with `mcp__server_name__`.

#### Configuration Options

Each MCP server can be configured with:
- **command**: The executable to run (e.g., `npx`, `uvx`, `docker`)
- **args**: List of arguments to pass to the command
- **env**: Environment variables as key-value pairs (optional)

#### Example Configurations

**GitHub Server (using Docker):**
```yaml
servers:
  github:
    command: docker
    args:
      - "run"
      - "--rm"
      - "-i"
      - "-e"
      - "GITHUB_PERSONAL_ACCESS_TOKEN"
      - "ghcr.io/github/github-mcp-server"
    env:
      GITHUB_PERSONAL_ACCESS_TOKEN: null  # Set via environment variable, will be prompted if not set
```

#### Fallback Behavior

If no `mcp.yaml` file is found, the agent will start without MCP servers (local tools only).
