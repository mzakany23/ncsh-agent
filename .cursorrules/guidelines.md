# Python Development Guidelines for Projects Using uv

## General Python Guidelines
- Follow PEP 8 standards for consistent and readable code.
- Use clear and descriptive names for variables and functions.
- Include comprehensive docstrings for modules, classes, and functions.
- Utilize type annotations wherever possible.

## Dependency and Environment Management with uv
- Use uv to manage virtual environments and dependencies.
- Development dependencies must be defined in `pyproject.toml` under `project.optional-dependencies.dev`.
- Production dependencies must be defined in `requirements.in`.
- Reference the detailed rules in `dependency-management.md`.
- Document dependency versions and environment setup clearly.

## Logging and Testing
- Use Python's logging module to enable effective debugging and monitoring.
- Write tests using pytest to ensure reliable functionality.
- Clearly specify how to run tests and the expected outcomes.

## Code Structure and Best Practices
- Favor modular and functional programming paradigms to enhance maintainability.
- Break code into small, reusable functions to avoid duplication.
- Ensure a clear separation between business logic, helper functions, and configuration.