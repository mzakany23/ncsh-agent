.PHONY: setup test clean format lint

# Default Python interpreter
PYTHON = python3
UV = uv

# Setup development environment
setup:
	$(UV) pip install -e .
	$(UV) pip sync requirements.txt

# Generate requirements.txt from requirements.in
requirements: requirements.in
	$(UV) pip compile requirements.in > requirements.txt

# Install dependencies
install: requirements.txt
	$(UV) pip sync

# Clean build artifacts
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	find . -name '*.pyc' -delete
	find . -name '__pycache__' -delete

# Format code
format:
	$(UV) run --active isort .
	$(UV) run --active black .

# Lint code
lint:
	$(UV) run --active flake8 main.py