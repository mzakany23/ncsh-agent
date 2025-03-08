# LLM and Tool Usage Guidelines

## Core Principles

- **Tools over direct implementation**: Prefer implementing functionality as Claude tools rather than hard-coding logic
- **Let the LLM think**: Provide Claude with the context and tools to solve problems, not rigid instructions
- **Map-reduce pattern**: Use a pattern where Claude maps problems to tools and then reduces tool outputs to a solution
- **Centralized tool definitions**: All tools should be defined in a consistent way in the tools module

## Claude Integration

### System Prompts

- Keep system prompts in the centralized `prompts.py` module
- Design prompts to be clear but not overly prescriptive
- Focus prompts on what Claude should achieve, not exactly how to achieve it
- Update prompts through the centralized module, not in individual code files

### Conversation Flow

- Use the conversation history appropriately for context
- Let Claude manage the conversation flow when possible
- Provide enough context for Claude to make informed decisions

## Tool Design

### Tool Implementation

1. **Each tool should do one thing well**
   - Follow single responsibility principle
   - Tools should have clear, focused functionality
   - Avoid tools that try to do too many things

2. **Tool interface consistency**
   - All tools should follow the same interface pattern
   - Tools should return structured results in a consistent format
   - Error handling should be consistent across tools

3. **Descriptive tool names and documentation**
   - Tool names should clearly indicate their purpose
   - Include detailed descriptions of what each tool does
   - Document parameters and return values thoroughly

### Tool Categories

1. **Data Retrieval Tools**
   - Tools that fetch or query data
   - Examples: `execute_sql`, `get_schema`, `check_date_range`

2. **Data Processing Tools**
   - Tools that analyze or transform data
   - Examples: `summarize_results`, `compact_dataset`

3. **Dataset Management Tools**
   - Tools for creating or managing datasets
   - Examples: `build_dataset`

4. **Validation Tools**
   - Tools for validating inputs or queries
   - Examples: `validate_sql`

5. **Task Completion Tools**
   - Tools for finalizing tasks
   - Examples: `complete_task`

## Preferred Patterns

### Let Claude Decide Which Tools to Use

Instead of hard-coding decision logic about which tool to use when, provide Claude with all available tools and let it decide based on the query and context.

**Good pattern:**
```python
# Provide all tools to Claude
tools = get_claude_tools()
response = client.messages.create(
    model="claude-3-7-sonnet-20250219",
    messages=messages,
    system=system_prompt,
    tools=tools,
)
```

### Tool-Based Problem Solving

When adding new functionality, implement it as a tool rather than embedding it directly in the agent or CLI code.

**Bad approach (embedding logic):**
```python
# Directly implementing date checking in the agent code
def run_agent(question):
    # Hard-coding date checking logic here
    if re.search(r"(Jan|Feb|Mar).*(\d{4})", question):
        # Direct implementation of date checking...
```

**Good approach (tool-based):**
```python
# Implementing a tool that Claude can call
def tool_check_date_range(tool_input):
    # Tool implementation for date checking

# Let Claude decide when to use it
tools = get_claude_tools()  # Includes check_date_range
```

### Map-Reduce Pattern

1. **Map phase**: Claude maps the problem to appropriate tools
2. **Execute phase**: System executes the tools Claude selected
3. **Reduce phase**: Claude integrates tool results into a coherent response

## Response Handling

- Process complete responses from Claude
- Handle tool calls appropriately
- Track metrics on tool usage
- Provide appropriate follow-up capability for incomplete responses