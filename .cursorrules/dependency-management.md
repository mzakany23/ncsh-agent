# Dependency Management Rules

## Location of Dependencies

1. **Development Dependencies**
   - All development dependencies must be defined in the `project.optional-dependencies.dev` section of `pyproject.toml`
   - This includes testing, linting, and formatting tools
   - Always specify minimum versions (e.g., `package>=x.y.z`)
   - Examples: pytest, black, isort, flake8

2. **Production Dependencies**
   - All production dependencies must be defined in `requirements.in`
   - Production dependencies are packages needed for the application to run in production
   - Always specify minimum versions (e.g., `package>=x.y.z`)
   - The `requirements.in` file is used to generate a pinned `requirements.txt` file

## Adding New Dependencies

1. **Development Dependencies**
   - To add a development dependency:
     1. Add it to `pyproject.toml` under `project.optional-dependencies.dev`
     2. Run `uv pip install -e .` to install the development package

2. **Production Dependencies**
   - To add a production dependency:
     1. Add it to `requirements.in`
     2. Run `make requirements` to generate an updated `requirements.txt`
     3. Run `make setup` to install the new production dependency

## Managing Dependencies

- Use `uv` for all dependency management operations
- Regularly update dependencies by checking for new versions
- Document any specific version requirements or constraints
- Keep development and production dependencies strictly separated