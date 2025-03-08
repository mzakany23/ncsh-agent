# Code Style and Organization Guidelines

## Basic Code Style

- Follow PEP 8 style guidelines for Python code
- Use 4 spaces for indentation, not tabs
- Maximum line length of 88 characters
- Use clear, descriptive variable and function names
- Use docstrings for all functions, classes, and modules
- Include type hints for function parameters and return values
- Add comments for complex sections of code

## Imports

- **No dead imports**: Remove any imported modules that are not used
- Group imports in the following order:
  1. Standard library imports
  2. Third-party library imports
  3. Local application imports
- Within each group, imports should be alphabetized
- Prefer explicit imports over wildcard imports (e.g., `from module import specific_function` is better than `from module import *`)

## Function and Class Design

- Follow the Single Responsibility Principle: functions and classes should do one thing and do it well
- Keep functions relatively short and focused
- Use meaningful parameter names that describe their purpose
- Default parameter values should be used when appropriate
- Return explicit values from functions rather than modifying variables through side effects

## Error Handling

- Use try/except blocks to handle specific exceptions, not broad exception catching
- Include meaningful error messages
- Log errors appropriately for debugging
- Consider the user experience when designing error handling

## File Organization

- Separate code into logical modules based on functionality
- Avoid monolithic files that contain too many different functions
- Use `__init__.py` files to expose a clean public API for each module
- Organize directory structure logically, with related functionality grouped together

## Example

Good module organization:

```python
# Import standard library modules
import os
import json
from typing import Dict, List

# Import third-party libraries
import pandas as pd
from rich.console import Console

# Import local modules
from analysis.database import DuckDBAnalyzer
from analysis.prompts import ANALYSIS_SYSTEM_PROMPT


def my_function(parameter: str) -> Dict:
    """
    Does one specific thing and does it well.

    Args:
        parameter: Description of parameter

    Returns:
        A dictionary containing the processed result
    """
    # Function implementation here...
    return result
```