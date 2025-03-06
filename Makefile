.PHONY: setup test clean format lint refresh-data query-llama setup-env debug-query

# Default Python interpreter
PYTHON = python3
UV = uv

# AWS S3 bucket for data
S3_BUCKET = s3://ncsh-app-data
S3_PATH = data/parquet
DATAFILE = data.parquet
DATA_DIR = analysis/data

# Setup development environment
setup:
	$(UV) pip install -e .
	$(UV) pip sync requirements.txt
	@mkdir -p $(DATA_DIR)

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
	$(UV) run --active flake8 cli.py

# Refresh data from AWS S3
refresh-data:
	@echo "Checking AWS S3 bucket $(S3_BUCKET)/$(S3_PATH) for data files..."
	aws s3 ls $(S3_BUCKET)/$(S3_PATH)
	@echo "Downloading $(DATAFILE) from S3 to $(DATA_DIR)/..."
	@mkdir -p $(DATA_DIR)
	aws s3 cp $(S3_BUCKET)/$(S3_PATH)/$(DATAFILE) $(DATA_DIR)/sample.parquet
	@echo "Successfully downloaded data to $(DATA_DIR)/sample.parquet"

# Run a query using the DuckDB Query Agent
query-llama:
	@if [ -z "$(query)" ]; then \
		echo "Error: Missing query parameter. Usage: make query-llama query=\"your query\"" && exit 1; \
	fi
	@if [ ! -f "$(DATA_DIR)/data.parquet" ]; then \
		echo "Warning: No data file found. Please check that the data exists at $(DATA_DIR)/data.parquet" && exit 1; \
	fi
	@echo "Running query: \"$(query)\""
	python cli.py -q "$(query)" -f "$(DATA_DIR)/data.parquet" --max_tokens 4000 --thinking_budget 3000

# Debug query agent code
debug-query: requirements
	@echo "Debugging DuckDB Query Agent code..."
	@$(UV) pip sync requirements.txt
	@echo "\nChecking analysis module imports:"
	$(PYTHON) -c "import sys; sys.path.append('.'); from analysis.duckdb_analyzer import get_schema, execute_sql, validate_sql; print('get_schema signature:', get_schema.__code__.co_varnames[:get_schema.__code__.co_argcount]); print('execute_sql signature:', execute_sql.__code__.co_varnames[:execute_sql.__code__.co_argcount]); print('validate_sql signature:', validate_sql.__code__.co_varnames[:validate_sql.__code__.co_argcount])"