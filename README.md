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

### 4. Activate the Virtual Environment

```bash
source .venv/bin/activate
```

Alternatively, you can run commands directly with uv without activating:
```bash
uv run python script.py
uv run jupyter notebook
```

## Dependencies

- **pydantic**: Data validation using Python type annotations
- **anthropic**: Official Python SDK for Anthropic's Claude API
- **jupyter**: Interactive notebook environment

## Usage

Open the main notebook:
```bash
uv run jupyter notebook llm-agent-from-scratch.ipynb
```

Or activate the virtual environment and run directly:
```bash
source .venv/bin/activate
jupyter notebook llm-agent-from-scratch.ipynb
```
