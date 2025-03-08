# Development Workflow Guidelines

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

## Testing

### Smoke Testing

- Run the smoke test script to quickly validate core functionality
- Verify that all tools work as expected
- Check that Claude can successfully use provided tools
- Ensure responses are complete and accurate

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
3. Test prompt changes thoroughly with the smoke test
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
- Use the smoke test to validate end-to-end functionality