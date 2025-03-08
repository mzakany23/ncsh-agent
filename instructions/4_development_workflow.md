# Development Workflow Guidelines

## Environment Setup

### Technology Stack Setup

- **Python 3.11+**: Required for all development
- **UV**: Use for dependency management instead of pip
  - Install dependencies: `uv install`
  - Run scripts: `uv run script_name.py`
- **DuckDB**: Used as the analytical database engine
  - No separate installation needed (packaged with dependencies)
- **Docker & Docker Compose**: For containerized development and deployment
  - Build image: `docker build -t ncsoccer-agent .`
  - Run with compose: `docker-compose up`
- **Streamlit**: For interactive UI development
  - Run the UI: `uv run streamlit run app.py`
- **LlamaIndex**: Configure in code for connecting Claude to our data
- **AWS**: Target deployment environment

### Environment Variables

Required environment variables:
- `ANTHROPIC_API_KEY`: For Claude API access
- Additional AWS credentials for deployment

## Git Practices

### Commits

- **Meaningful commit messages**: Commit messages should clearly describe what changes were made and why
- **Atomic commits**: Each commit should represent a single logical change
- **Present tense**: Use present tense in commit messages (e.g., "Add feature" not "Added feature")
- **Reference issues**: Reference relevant issue numbers in commit messages when applicable

Examples:
- ✅ "Add check_date_range tool for verifying data availability"
- ✅ "Fix JSON parsing error in database query function"
- ❌ "Fixed stuff"
- ❌ "WIP"

### Branching

- Use feature branches for new development
- Keep the main branch stable
- Pull request reviews before merging to main
- Delete branches after merging

## Code Reviews

- Check for adherence to code style guidelines
- Verify proper module organization
- Ensure no business logic in UI layers
- Look for appropriate tool usage vs. direct implementation
- Confirm adequate error handling
- Validate documentation completeness

## Examples Framework

The project includes a sophisticated examples framework for testing and demonstrating functionality.

### Running Examples

- Run a default example: `python -m examples`
- Run a specific example: `python -m examples --example=future_dates`
- Run with a custom query: `python -m examples "How did Key West perform in January 2025?"`
- Run an example script directly: `python -m examples.1_basic`

### Example Framework Structure

- `examples/__init__.py`: Contains the `BaseSmokeTest` class and package entry point
- `examples/1_basic.py`, `examples/2_future_dates.py`, etc.: Specific test scenarios
- Examples are numbered to ensure they appear in a logical order

### Creating a New Example

1. Create a new file in the `examples` directory with a numbered prefix: `N_example_name.py`
2. Import the base class: `from examples import BaseSmokeTest, console`
3. Create a subclass of `BaseSmokeTest` with your custom functionality
4. Implement the `run_default_tests` method with your specific test queries
5. Add a `main()` function for direct execution (optional)

Example:

```python
"""
Example description.
"""

import os
import sys
from examples import BaseSmokeTest, console

class MyExample(BaseSmokeTest):
    """My example class."""

    def __init__(self, parquet_file: str = "analysis/data/data.parquet"):
        """Initialize the example."""
        super().__init__(parquet_file)

    def run_default_tests(self):
        """Run default test queries."""
        queries = [
            "First test query",
            "Second test query"
        ]

        console.print("[bold magenta]Running My Example Queries[/bold magenta]\n")
        self.run_queries(queries)

def main():
    """Run the example."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        console.print("[red]Error: ANTHROPIC_API_KEY environment variable is not set.[/red]")
        sys.exit(1)

    example = MyExample()

    if len(sys.argv) > 1:
        example.run_from_args()
    else:
        example.run_default_tests()

if __name__ == "__main__":
    main()
```

### Framework Features

The examples framework provides:

1. **Standardized Query Processing**:
   - Consistent handling of queries and responses
   - Conversation history tracking
   - Tool call tracking

2. **Response Evaluation**:
   - Quality assessment based on response length and content
   - Completeness detection
   - Response timing metrics

3. **Summary Reporting**:
   - Success/failure status
   - Incomplete response counts
   - Average tool call statistics

4. **Easy Extensions**:
   - Extend the `BaseSmokeTest` class for custom test scenarios
   - Override methods for specialized behavior
   - Add new methods for additional functionality

### Registering a New Example

After creating a new example, register it in the examples package by:

1. Add your example class to `examples/__init__.py` imports
2. Add your example to the `run()` function's example selector
3. Update the `__all__` list to include your new class

## Testing

### Using the Examples Framework

- Use the examples framework for quick testing of agent functionality
- Create specific examples for edge cases or complex scenarios
- Run all examples periodically to verify overall system health

### Unit Testing

- Write unit tests for all core functionality
- Test edge cases and error handling
- Mock external dependencies
- Aim for high test coverage of business logic

## Extending the Project

### Adding New Tools

1. Implement the tool function in the appropriate module
2. Add the tool definition to `get_claude_tools()` in `claude_tools.py`
3. Add the tool mapping in `get_tool_mapping()` in `claude_tools.py`
4. Update system prompts if needed to inform Claude about the new tool
5. Add tests for the new tool

Example:
```python
# 1. Implement the tool function
def tool_new_functionality(tool_input: Dict) -> Dict:
    """Implementation of the new tool."""
    # Tool implementation here
    return {"result": result}

# 2 & 3. Add to tool definitions and mapping
def get_claude_tools():
    tools = [
        # ... existing tools ...
        {
            "name": "new_functionality",
            "description": "Description of what the new tool does",
            "input_schema": {
                "type": "object",
                "properties": {
                    "param1": {
                        "type": "string",
                        "description": "Description of parameter",
                    },
                },
                "required": ["param1"],
            },
        },
    ]
    return tools

def get_tool_mapping():
    return {
        # ... existing mappings ...
        "new_functionality": tool_new_functionality,
    }
```

### Adding New Modules

1. Create the new module file with appropriate functionality
2. Update `__init__.py` to expose the necessary functions
3. Follow the established pattern for module organization
4. Keep business logic in the module, not in interface layers
5. Integrate with existing modules as needed

### Modifying System Prompts

1. Update the prompts in the centralized `prompts.py` file
2. Ensure changes are consistent with the overall design
3. Test prompt changes thoroughly with the examples framework
4. Document the purpose of prompt changes

## Troubleshooting

### Common Issues

- **Incomplete Claude responses**: Check if the prompt needs refinement or if tools need better documentation
- **Tool execution errors**: Verify tool implementation and error handling
- **Module integration issues**: Check import paths and module dependencies

### Debugging

- Use the rich console output for detailed logging
- Check exception tracebacks for error details
- Test tools individually before integration
- Use the examples framework to validate end-to-end functionality