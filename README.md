# My Project

A Python project using UV for dependency management.

## Setup

This project uses [uv](https://github.com/astral-sh/uv) for Python package management and virtual environments.

### Prerequisites

- Python 3.8 or higher
- uv (`pip install uv`)

### Development Setup

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd my_project
   ```

2. Set up the development environment:
   ```bash
   make setup
   ```

This will:
- Install the project in development mode
- Install all dependencies from requirements.txt

## Development Tools

The project includes several development tools:

- **Black**: Code formatting
- **isort**: Import sorting
- **flake8**: Code linting

You can run these tools using the following commands:

```bash
# Format code
make format

# Lint code
make lint
```

## Dependency Management

This project follows specific conventions for dependency management:

- **Development dependencies** are defined in `pyproject.toml` under `project.optional-dependencies.dev`
- **Production dependencies** are defined in `requirements.in` and compiled to `requirements.txt`

To add a new production dependency:
1. Add it to `requirements.in`
2. Run `make requirements` to update `requirements.txt`
3. Run `make setup` to install the dependency

To add a new development dependency:
1. Add it to `pyproject.toml` under `project.optional-dependencies.dev`
2. Run `uv pip install -e .` to install the dependency

## License

[MIT License](LICENSE)