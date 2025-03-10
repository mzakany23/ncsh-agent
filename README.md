# DuckDB Soccer Analysis Agent with Claude 3.7

![NC Soccer Agent Interface](ncsoccer.png)

An agentic approach to query soccer match data using Claude 3.7's tool calling capabilities. This project allows you to ask natural language questions about soccer match data stored in parquet files and get accurate SQL-based answers.

## Features

- **Natural Language to SQL**: Translate questions like "how did Key West FC do in 2025 Feb" into proper SQL queries
- **Team Name Fuzzy Matching**: Automatically matches ambiguous team names to their database equivalents
- **Schema Understanding**: Automatically extracts and understands parquet file schema
- **SQL Validation**: Validates generated SQL before execution to prevent errors
- **Recursive Tool Calling**: Advanced pipeline that allows Claude to use multiple tools in sequence
- **Interactive UI**: Streamlit-based user interface for easy interaction
- **Dataset Management**: Create and select team-specific datasets for faster, context-efficient analysis

## Architecture

The project uses an intelligent agent architecture with the following components:

- **Claude 3.7 API**: Powers the reasoning and natural language understanding
- **DuckDB**: Fast in-process SQL engine for querying parquet files
- **Tools Framework**: A comprehensive set of tools for Claude to interact with the database
- **Analysis Module**: Enhanced data analysis capabilities for soccer match data
- **Streamlit UI**: Web interface for interactive querying
- **Dataset Context Mode**: Alternative lightweight mode for faster responses with pre-loaded data

## Setup

This project uses [uv](https://github.com/astral-sh/uv) for Python package management and virtual environments.

### Prerequisites

- Python 3.8 or higher
- uv (`pip install uv`)
- An Anthropic API key for Claude 3.7

### Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd ncsoccer-agent
   ```

2. Set up the environment:
   ```bash
   uv venv
   uv pip install -e .
   ```

3. Set your Anthropic API key:
   ```bash
   export ANTHROPIC_API_KEY=your_api_key_here
   ```

4. Download the sample data:
   ```bash
   make refresh-data
   ```

## Usage

### Command Line Interface

Run the query agent with a natural language question:

```bash
uv run cli.py query "How did Key West FC do in February 2025?"
```

### Streamlit UI

Launch the web interface for interactive querying:

```bash
cd ui && python -m streamlit run app.py
```

#### Dataset Mode

In the Streamlit UI, you can use the Dataset Management feature in the sidebar to:

1. **Create New Datasets**: Generate LLM-optimized datasets for specific teams
2. **Select Existing Datasets**: Choose from previously created datasets
3. **Chat with Dataset Context**: Ask questions directly about the selected dataset

This feature provides:
- **Faster Responses**: Without the overhead of running SQL queries each time
- **Focused Analysis**: Interactions are specifically about the loaded dataset
- **Simplified Context**: Using a smaller, targeted context window for more efficient processing
- **Smart Query Routing**: Intelligently uses the dataset context for most questions, only switching to full SQL queries when necessary for global analysis

The system intelligently determines when a question is about the loaded dataset versus when it requires broader analysis. Questions like "what was the biggest win?" will use the loaded dataset, while questions like "how does this compare to all teams historically?" will use the full database with SQL queries.

### Using Dataset Mode in Streamlit UI

1. In the sidebar, enter dataset instructions like "Create a 2025 Key West dataset" or "Internazionale matches in January"
2. Click "Create Dataset" to generate an optimized dataset with time period filtering
3. The dataset will load automatically and be displayed in the chat
4. Ask questions about the dataset: "How many games did they win?" or "What was their biggest victory?"
5. For statistical questions, the system will automatically query the full database
6. For simple questions, you'll get faster responses using the pre-loaded dataset context

## Project Structure

- `cli.py`: Command-line interface for the agent
- `analysis/`: Core analysis functionality
  - `agent.py`: The main agent implementation with recursive tool calling
  - `database.py`: DuckDB-specific analysis tools
  - `tools/`: Tool implementations for Claude 3.7
    - `claude_tools.py`: Tool definitions and implementations
- `ui/`: Streamlit-based web interface
  - `app.py`: Main Streamlit application with dataset management
  - `streamlit_agent.py`: Streamlit-compatible agent implementation
  - `data/`: Directory for storing team-specific datasets

## Examples

### Team Performance Analysis

```bash
uv run cli.py query "Compare the performance of Key West FC and BDE in February 2025"
```

### Finding Match Results

```bash
uv run cli.py query "Show me all matches where Key West FC scored more than 5 goals"
```

### Creating Team Datasets

```bash
uv run cli.py team "Key West FC"
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

[MIT License](LICENSE)

# NC Soccer Hudson - Match Analysis Agent

This repository contains the Match Analysis Agent for NC Soccer Hudson, powered by AI to help analyze soccer matches.

## Architecture

The application is built using:
- Streamlit for the web interface
- Anthropic Claude AI for match analysis
- Nginx as a reverse proxy with basic authentication
- Docker for containerization and deployment

## Local Development

### Prerequisites

1. Docker and Docker Compose installed
2. Anthropic API key
3. Git

### Setup and Run

1. Clone the repository:
   ```bash
   git clone https://github.com/mzakany23/ncsh-agent.git
   cd ncsh-agent
   ```

2. Set up the Nginx configuration and basic auth:
   ```bash
   mkdir -p nginx
   htpasswd -bc nginx/.htpasswd ncsoccer password123

   cat > nginx/nginx.conf << EOF
   server {
       listen 80 default_server;
       server_name _;
       client_max_body_size 100M;

       location / {
           auth_basic "NC Soccer Hudson - Match Analysis Agent";
           auth_basic_user_file /etc/nginx/.htpasswd;
           proxy_pass http://streamlit:8501;
           proxy_http_version 1.1;
           proxy_set_header Upgrade \$http_upgrade;
           proxy_set_header Connection "upgrade";
           proxy_set_header Host \$host;
           proxy_set_header X-Real-IP \$remote_addr;
           proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto \$scheme;
           proxy_read_timeout 86400;
           proxy_cache_bypass \$http_upgrade;
       }
   }
   EOF
   ```

3. Set your Anthropic API key:
   ```bash
   export ANTHROPIC_API_KEY=your-anthropic-api-key
   ```

4. Start the application with Docker Compose:
   ```bash
   docker-compose up
   ```

5. Access the application at http://localhost with the following credentials:
   - Username: `ncsoccer`
   - Password: `password123` (or the value you set in step 2)

### Development Mode

For active development, uncomment the volumes line in `docker-compose.yml` to enable hot reloading of changes:

```yaml
volumes:
  - ./ui:/app
```

## AWS EC2 Deployment

### Using Terraform (Recommended)

For automated deployment to AWS EC2, see the [Terraform EC2 README](terraform/ec2/README.md).

### Manual Deployment to EC2

If you prefer to manually deploy to an existing EC2 instance:

1. SSH into your EC2 instance:
   ```bash
   ssh -i your-key.pem ec2-user@your-ec2-ip
   ```

2. Install Docker:
   ```bash
   sudo amazon-linux-extras install -y docker
   sudo systemctl start docker
   sudo systemctl enable docker
   ```

3. Install Nginx:
   ```bash
   sudo amazon-linux-extras install -y nginx1
   ```

4. Clone the repository:
   ```bash
   git clone https://github.com/mzakany23/ncsh-agent.git ~/streamlit-app
   ```

5. Set up Nginx configuration:
   ```bash
   sudo cat > /etc/nginx/conf.d/streamlit.conf << 'EOF'
   server {
       listen 80 default_server;
       server_name _;
       client_max_body_size 100M;

       location / {
           auth_basic "NC Soccer Hudson - Match Analysis Agent";
           auth_basic_user_file /etc/nginx/.htpasswd;
           proxy_pass http://localhost:8501;
           proxy_http_version 1.1;
           proxy_set_header Upgrade $http_upgrade;
           proxy_set_header Connection "upgrade";
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
           proxy_read_timeout 86400;
           proxy_cache_bypass $http_upgrade;
       }
   }
   EOF
   ```

6. Create basic auth credentials:
   ```bash
   sudo yum install -y httpd-tools
   sudo htpasswd -bc /etc/nginx/.htpasswd ncsoccer your-password
   ```

7. Build and run the Docker container:
   ```bash
   cd ~/streamlit-app
   sudo docker build -t ncsoccer-ui -f ui/Dockerfile .
   sudo docker run -d --name ncsoccer-ui --restart unless-stopped \
     -p 8501:8501 \
     -e ANTHROPIC_API_KEY="your-anthropic-api-key" \
     -e BASIC_AUTH_USERNAME=ncsoccer \
     -e BASIC_AUTH_PASSWORD="your-password" \
     ncsoccer-ui
   ```

8. Start Nginx:
   ```bash
   sudo systemctl enable nginx
   sudo systemctl start nginx
   ```

9. Access your application at http://your-ec2-ip with the credentials you specified.

## Troubleshooting

### Local Development

1. If the Docker container fails to start:
   ```bash
   docker logs ncsoccer-ui
   ```

2. If Nginx fails to start:
   ```bash
   docker logs ncsh-agent_nginx_1
   ```

3. To rebuild the Docker image:
   ```bash
   docker-compose down
   docker-compose build --no-cache
   docker-compose up
   ```

### EC2 Deployment

See the [Terraform EC2 README](terraform/ec2/README.md#troubleshooting) for detailed troubleshooting steps for EC2 deployments.