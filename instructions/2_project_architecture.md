# Project Architecture Guidelines

## Core Principles

- **Separation of concerns**: Each component should have a single, well-defined responsibility
- **Modular design**: Code should be organized into cohesive modules that can be developed and tested independently
- **Clean interfaces**: Modules should expose clear, well-documented interfaces
- **Loose coupling**: Minimize dependencies between modules
- **No business logic in UI layers**: UI components should only handle presentation, not business logic

## Module Structure

Our project follows a modular architecture with the following key components:

### Core Modules

1. **`analysis/database.py`**
   - Responsible for all database operations
   - Includes the `DuckDBAnalyzer` class for database interaction
   - Provides functions for executing queries, schema extraction, and data manipulation
   - All SQL operations should be centralized here

2. **`analysis/prompts.py`**
   - Contains all system prompts used for interacting with the LLM
   - Centralizes prompt management to ensure consistency
   - Promotes reuse of prompt templates

3. **`analysis/agent.py`**
   - Contains the core agent functionality
   - Manages interactions with the LLM
   - Handles conversation flow and tool calls
   - Processes LLM responses

4. **`analysis/datasets.py`**
   - Handles dataset operations
   - Provides functions for creating, filtering, and manipulating datasets
   - Formats and presents dataset information

5. **`analysis/tools/claude_tools.py`**
   - Defines tools that Claude can use via the Anthropic API
   - Implements adapters for tool functions
   - Maps tool definitions to their implementations

### Interface Layers

1. **`cli.py`**
   - Thin wrapper around core functionality
   - Should NOT contain business logic
   - Simply parses command-line arguments and delegates to appropriate modules
   - Formats outputs for terminal display

2. **Web/UI Components**
   - Should only handle presentation and user interaction
   - Delegate all business logic to core modules
   - Focus on providing a clean, intuitive interface

## Design Rules

1. **CLI is just a wrapper**
   - The CLI should be minimal and only focus on the user interface
   - All business logic should be in the appropriate core modules
   - The CLI should import functionality from core modules, not implement it

2. **File size limits**
   - If a file exceeds 500 lines, it's likely doing too much and should be split
   - Large file size is a "code smell" that suggests poor separation of concerns

3. **Proper module dependencies**
   - Higher-level modules (CLI, web interfaces) depend on core modules
   - Core modules should not depend on interface modules
   - Circular dependencies should be avoided

4. **Organized imports**
   - Only import what you need
   - Use explicit imports rather than wildcard imports
   - Group imports by standard library, third-party, and local modules

## Example: Proper Separation of Concerns

**Bad Example (mixing concerns):**
```python
# cli.py - Too much business logic in the interface layer
def process_query(question, parquet_file):
    # Directly implementing business logic here is bad!
    conn = duckdb.connect(database=':memory:')
    conn.execute(f"CREATE TABLE input_data AS SELECT * FROM '{parquet_file}'")
    # More direct database manipulation...
```

**Good Example (proper separation):**
```python
# cli.py - Clean interface layer
def process_query(question, parquet_file):
    # Just delegate to the appropriate module
    return agent.run_agent(question, parquet_file)

# analysis/agent.py - Business logic in the right place
def run_agent(question, parquet_file):
    # Handle the actual business logic here
    analyzer = database.DuckDBAnalyzer(parquet_file)
    # Process the query...
```