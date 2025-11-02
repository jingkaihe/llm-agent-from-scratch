# LLM Agent From Scratch

A project for building LLM agents using Python, Pydantic, and Anthropic's API.

## Prerequisites

- Python 3.8 or higher
- `uv` package manager

## Setup Instructions

### 1. Install uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Alternative (via pip):**
```bash
pip install uv
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

#### Creating an MCP Configuration

1. Copy the example configuration:
   ```bash
   cp mcp.yaml.example mcp.yaml
   ```

2. Edit `mcp.yaml` to customize your MCP servers:
   ```yaml
   servers:
     - command: npx
       args:
         - "-y"
         - "@modelcontextprotocol/server-filesystem"
         - "/path/to/directory"
       cwd: "."  # Working directory (supports ~ and relative paths)
       env: null  # Environment variables (optional)
   ```

#### Configuration Options

Each MCP server can be configured with:
- **command**: The executable to run (e.g., `npx`, `uvx`, `python`)
- **args**: List of arguments to pass to the command
- **cwd**: Working directory for the server process (optional, supports `~` expansion)
- **env**: Environment variables as key-value pairs (optional)

#### Available MCP Servers

- **@modelcontextprotocol/server-filesystem**: File system access tools
- **mcp-server-git**: Git repository operations
- **mcp-server-sqlite**: SQLite database access
- **@modelcontextprotocol/server-github**: GitHub API integration

See `mcp.yaml.example` for more examples.

#### Fallback Behavior

If no `mcp.yaml` file is found, the agent will use a default configuration with a filesystem server pointing to `/tmp`.
