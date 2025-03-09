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
  ami                    = "ami-0c55b159cbfafe1f0"  # Amazon Linux 2 AMI (update with latest)
  instance_type          = "t2.micro"  # Free tier eligible
  key_name               = var.key_name  # Create this in AWS first
  vpc_security_group_ids = [aws_security_group.streamlit_sg.id]

  # Install required software via user_data
  user_data = <<-EOF
    #!/bin/bash
    yum update -y
    yum install -y nginx python3 python3-pip git htpasswd

    # Configure Nginx with Basic Auth
    cat > /etc/nginx/conf.d/streamlit.conf << 'NGINXCONF'
    server {
        listen 80 default_server;
        server_name _;
        client_max_body_size 100M;

        location / {
            auth_basic "Restricted Access";
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

    # Create a password file for Nginx Basic Auth
    htpasswd -bc /etc/nginx/.htpasswd ncsoccer ${var.basic_auth_password}

    # Configure Streamlit as a service
    cat > /etc/systemd/system/streamlit.service << 'STREAMLITSERVICE'
    [Unit]
    Description=NC Soccer Hudson - Match Analysis Agent
    After=network.target

    [Service]
    User=ec2-user
    WorkingDirectory=/home/ec2-user/streamlit-app
    ExecStart=/usr/bin/python3 -m streamlit run app.py --server.port=8501 --server.address=0.0.0.0
    Restart=always
    Environment="ANTHROPIC_API_KEY=${var.anthropic_api_key}"

    [Install]
    WantedBy=multi-user.target
    STREAMLITSERVICE

    mkdir -p /home/ec2-user/streamlit-app
    chown -R ec2-user:ec2-user /home/ec2-user/streamlit-app

    # Ensure Nginx can start after reboot
    systemctl enable nginx
    systemctl start nginx

    # Disable SELinux if it's preventing connections
    setenforce 0 || true
    sed -i 's/SELINUX=enforcing/SELINUX=permissive/g' /etc/selinux/config || true

    # Open firewall ports if firewalld is installed
    if command -v firewall-cmd &> /dev/null; then
        firewall-cmd --permanent --add-service=http
        firewall-cmd --permanent --add-service=https
        firewall-cmd --reload
    fi
  EOF

  tags = {
    Name = "ncsoccer-streamlit-server"
  }
}