.PHONY: setup test clean format lint refresh-data query-llama setup-env debug-query create-dataset

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
	
	# First create a backup of the current data if it exists
	@if [ -f "$(DATA_DIR)/data.parquet" ]; then \
		cp $(DATA_DIR)/data.parquet $(DATA_DIR)/data.backup.parquet; \
		echo "Created backup of existing data file"; \
	fi
	
	# Download main data file
	aws s3 cp $(S3_BUCKET)/$(S3_PATH)/$(DATAFILE) $(DATA_DIR)/data.parquet
	@echo "Successfully downloaded data to $(DATA_DIR)/data.parquet"
	
	# Check for additional datasets in the versioned directories
	@echo "Checking for additional datasets in versioned directories..."
	aws s3 ls $(S3_BUCKET)/$(S3_PATH)/ | grep "^PRE" | awk '{print $2}' | while read version; do \
		echo "Found version directory: $$version"; \
		mkdir -p $(DATA_DIR)/$$version; \
		aws s3 sync $(S3_BUCKET)/$(S3_PATH)/$$version $(DATA_DIR)/$$version; \
		echo "Synced files from $$version"; \
	done
	
	# List all downloaded datasets
	@echo "All available datasets:"
	@find $(DATA_DIR) -name "*.parquet" | sort

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

# Create a team-specific dataset
create-dataset:
	@if [ -z "$(team)" ]; then \
		echo "Error: Missing team parameter. Usage: make create-dataset team=\"Team Name\"" && exit 1; \
	fi
	@if [ ! -f "$(DATA_DIR)/data.parquet" ]; then \
		echo "Warning: No data file found. Please check that the data exists at $(DATA_DIR)/data.parquet" && exit 1; \
	fi
	@echo "Creating dataset for team: \"$(team)\""
	python cli.py -q "Create a dataset for team $(team)$(if $(output), and save it to $(output))" -f "$(DATA_DIR)/data.parquet"

# Create a compact dataset representation optimized for Claude's context window
compact-dataset:
	@if [ ! -f "$(file)" ] && [ ! -f "$(DATA_DIR)/data.parquet" ]; then \
		echo "Warning: No data file found. Please specify a file with file=\"path/to/file.parquet\" or ensure data exists at $(DATA_DIR)/data.parquet" && exit 1; \
	fi
	@echo "Creating compact dataset representation..."
	python cli.py -q "Create a compact dataset representation in $(if $(format),$(format),compact) format" -f "$(if $(file),$(file),$(DATA_DIR)/data.parquet)"