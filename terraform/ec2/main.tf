terraform {
  backend "s3" {
    bucket         = "ncsoccer-tfstate-siu66w32"
    key            = "ec2/terraform.tfstate"
    region         = "us-east-2"
    dynamodb_table = "ncsoccer-terraform-locks"
    encrypt        = true
  }
}

provider "aws" {
  region = "us-east-2"  # Choose your preferred region
}

# VPC and Security Group
resource "aws_security_group" "streamlit_sg" {
  name        = "streamlit-sg"
  description = "Allow HTTP and SSH traffic"

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]  # Restrict to your IP for production
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# EC2 Instance
resource "aws_instance" "streamlit_server" {
  ami                    = var.ami_id
  instance_type          = var.instance_type
  key_name               = var.key_name
  vpc_security_group_ids = [aws_security_group.streamlit_sg.id]

  # Install required software via user_data
  user_data = <<-EOF
    #!/bin/bash
    set -e

    echo "===== Starting deployment setup: $(date) ====="

    # Update system packages
    echo "Updating system packages..."
    yum update -y

    # Install Docker and dependencies
    echo "Installing Docker..."
    amazon-linux-extras install -y docker
    yum install -y git httpd-tools

    # Start and enable Docker
    echo "Starting Docker service..."
    systemctl start docker
    systemctl enable docker

    # Create application directories
    echo "Setting up application directories..."
    mkdir -p /home/ec2-user/streamlit-app
    chown -R ec2-user:ec2-user /home/ec2-user/streamlit-app

    # Clone the application code from GitHub
    echo "Cloning application code..."
    git clone https://github.com/mzakany23/ncsh-agent.git /home/ec2-user/streamlit-app
    chown -R ec2-user:ec2-user /home/ec2-user/streamlit-app

    # Configure Nginx with Basic Auth
    echo "Configuring Nginx with Basic Auth..."
    amazon-linux-extras install -y nginx1
    cat > /etc/nginx/conf.d/streamlit.conf << 'NGINXCONF'
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
    NGINXCONF

    # Create htpasswd file for Nginx Basic Auth
    echo "Creating basic auth credentials..."
    htpasswd -bc /etc/nginx/.htpasswd ncsoccer "${var.basic_auth_password}"

    # Build and run Docker container
    echo "Building and running Docker container..."
    cd /home/ec2-user/streamlit-app
    docker build -t ncsoccer-ui -f ui/Dockerfile .
    docker run -d --name ncsoccer-ui --restart unless-stopped \
      -p 8501:8501 \
      -e ANTHROPIC_API_KEY="${var.anthropic_api_key}" \
      -e BASIC_AUTH_USERNAME=ncsoccer \
      -e BASIC_AUTH_PASSWORD="${var.basic_auth_password}" \
      ncsoccer-ui

    # Start and enable Nginx
    echo "Starting Nginx..."
    systemctl enable nginx
    systemctl start nginx

    # Disable SELinux to avoid permission issues
    echo "Configuring SELinux..."
    setenforce 0 || true
    sed -i 's/SELINUX=enforcing/SELINUX=permissive/g' /etc/selinux/config || true

    # Configure firewall if needed
    if command -v firewall-cmd &> /dev/null; then
        echo "Configuring firewall..."
        firewall-cmd --permanent --add-service=http
        firewall-cmd --permanent --add-service=https
        firewall-cmd --reload
    fi

    echo "===== Deployment setup finished: $(date) ====="
  EOF

  tags = {
    Name = "ncsoccer-streamlit-server"
  }
}