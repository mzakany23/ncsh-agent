# Cursor-Specific Instructions

## Code Generation Guidelines
- Generate code that strictly adheres to the Python guidelines in this project.
- Follow PEP 8 formatting and style conventions consistently.
- Include proper docstrings and type annotations in all new code.
- Break complex functions into smaller, more manageable pieces.

## Tool Usage
- Prefer using `uv` commands for Python package management and script execution.
- Use `uv add [package]` for adding new dependencies.
- Use `uv run [script]` for executing Python scripts.
- Reference the Makefile targets for standard development tasks.

## Project Structure
- Maintain modular code organization with clear separation of concerns.
- Keep files focused on a single responsibility.
- Ensure consistent import ordering using isort conventions.
- Format code using black with a line length of 88 characters.

## Code Quality
- Write code that passes flake8 linting without warnings.
- Favor explicit over implicit code constructs.
- Use meaningful variable and function names that indicate purpose.
- Include comments for complex logic or algorithms.

## Reference
- Reference this .cursorrules directory to check that all new code aligns with the project's standards.
- Customize and extend these guidelines as needed over time.