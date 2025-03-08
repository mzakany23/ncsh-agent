# NC Soccer Agent Project Overview

## Project Description

The NC Soccer Agent is an agentic system built on Claude that provides data analysis for soccer match data. It's designed to serve as a flexible, tool-based framework that leverages Claude's capabilities to understand natural language queries, translate them to appropriate database operations, and present results in a human-friendly format.

## Technology Stack

The project uses the following technologies:

- **Python 3.11+**: Core programming language
- **DuckDB**: In-memory analytical database for efficient data processing
- **LlamaIndex**: Framework for connecting custom data to LLMs
- **Anthropic Claude**: Large language model for natural language processing
- **Streamlit**: Frontend for interactive web applications
- **Docker & Docker Compose**: Containerization and orchestration
- **AWS**: Cloud deployment platform
- **UV**: Modern Python packaging and dependency management tool

## Core Philosophy

This project follows several key principles:

1. **Agentic Design**: The system follows an agentic pattern where Claude makes decisions about which tools to use based on the user's query.

2. **Tool-Based Approach**: Rather than hard-coding logic, we implement functionality as tools that Claude can call. This creates a flexible, extensible system that can evolve with minimal code changes.

3. **Map-Reduce Pattern**: Claude maps the problem to appropriate tools, the system executes those tools, and Claude reduces the results into a coherent response.

4. **Modular Architecture**: The codebase is organized into focused modules with clear responsibilities, making it easier to maintain and extend.

5. **Separation of Concerns**: Business logic is kept separate from presentation layers. The CLI and UI components are thin wrappers that delegate to the core modules.

## Getting Started

1. Install dependencies using `uv install`
2. Run an example to verify the setup: `python -m examples`
3. Use the CLI tool to interact with the agent: `uv run cli.py query "How did Key West perform in February 2025?"`

## Project Structure

- `analysis/`: Core business logic and tools
  - `database.py`: Database operations and queries
  - `agent.py`: LLM interaction and tool coordination
  - `prompts.py`: System prompts for Claude
  - `datasets.py`: Dataset management operations
  - `tools/`: Tool implementations for Claude
- `cli.py`: Command-line interface
- `examples/`: Test and example scripts
  - `__init__.py`: Base testing framework and package entry point
  - `1_basic.py`: Basic demonstration of the agent
  - `2_future_dates.py`: Tests for handling future date queries
  - Additional examples follow the pattern: `N_example_name.py`

## Examples Framework

The project includes a flexible testing and example framework:

- Run an example: `python -m examples`
- Select a specific example: `python -m examples --example=future_dates`
- Run with a custom query: `python -m examples "How did Key West perform in January 2025?"`

This framework provides consistent testing capabilities with:
- Standardized query processing
- Response quality evaluation
- Performance metrics tracking
- Test summary reporting

## Documentation

The project is documented through this instruction series:

1. [Code Style and Organization](1_code_style_and_organization.md) - Guidelines for code formatting, structure, and organization
2. [Project Architecture](2_project_architecture.md) - Overview of the modular architecture and component responsibilities
3. [LLM and Tool Usage](3_llm_and_tool_usage.md) - Patterns for working with Claude and implementing tools
4. [Development Workflow](4_development_workflow.md) - Processes for extending, testing, and maintaining the project

## Key Concepts

### Tools

Tools are the primary mechanism for extending the system's capabilities. Each tool:
- Has a single, well-defined purpose
- Follows a consistent interface pattern
- Is registered in the `claude_tools.py` module
- Can be called by Claude when appropriate

### Prompts

System prompts guide Claude's behavior and are centralized in the `prompts.py` module to ensure consistency and reusability.

### Agent

The agent module coordinates interactions with Claude, handling:
- Query processing
- Tool call execution
- Response formatting
- Conversation history management

## Project Goals

The project aims to:
1. Demonstrate effective integration of Claude into a data analysis system
2. Provide a flexible framework for natural language data querying
3. Showcase best practices for building agentic systems
4. Serve as a reference architecture for similar projects