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
  description = "Allow HTTP, HTTPS and SSH traffic"

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

# S3 Data Bucket IAM Policy - Only allow access to specific bucket and path
resource "aws_iam_policy" "s3_data_access" {
  name        = "ncsoccer-s3-data-access"
  description = "Allow access to specific S3 data bucket and path"

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Action = [
          "s3:GetObject",
          "s3:ListBucket"
        ],
        Resource = [
          "arn:aws:s3:::ncsh-app-data",
          "arn:aws:s3:::ncsh-app-data/data/parquet/*"
        ]
      }
    ]
  })
}

# IAM Role for EC2
resource "aws_iam_role" "ec2_role" {
  name = "ncsoccer-ec2-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Principal = {
          Service = "ec2.amazonaws.com"
        },
        Action = "sts:AssumeRole"
      }
    ]
  })
}

# Attach the S3 data access policy to the role
resource "aws_iam_role_policy_attachment" "s3_data_access_attachment" {
  role       = aws_iam_role.ec2_role.name
  policy_arn = aws_iam_policy.s3_data_access.arn
}

# Create instance profile
resource "aws_iam_instance_profile" "ec2_profile" {
  name = "ncsoccer-ec2-profile"
  role = aws_iam_role.ec2_role.name
}

# Route 53 Domain Setup (if using a new domain)
resource "aws_route53_zone" "main" {
  count = var.enable_domain_and_tls && var.create_new_domain ? 1 : 0
  name  = var.domain_name
}

# Use existing Route 53 hosted zone (if using existing domain)
data "aws_route53_zone" "existing" {
  count = var.enable_domain_and_tls && !var.create_new_domain ? 1 : 0
  name  = var.domain_name
}

locals {
  zone_id = var.enable_domain_and_tls ? (var.create_new_domain ? aws_route53_zone.main[0].zone_id : data.aws_route53_zone.existing[0].zone_id) : ""

  # User data template - with TLS enabled
  user_data_tls_enabled = <<-EOF
    #!/bin/bash
    set -e

    echo "===== Starting deployment setup: $(date) ====="

    # Update system packages
    echo "Updating system packages..."
    yum update -y

    # Install Docker and dependencies
    echo "Installing Docker..."
    amazon-linux-extras install -y docker
    yum install -y git httpd-tools certbot

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

    # Configure Nginx with Basic Auth and SSL
    echo "Configuring Nginx with Basic Auth and SSL..."
    amazon-linux-extras install -y nginx1
    cat > /etc/nginx/conf.d/streamlit.conf << 'NGINXCONF'
    server {
        listen 80 default_server;
        server_name ${var.domain_name} www.${var.domain_name};
        client_max_body_size 100M;

        # Redirect to HTTPS
        location / {
            return 301 https://$host$request_uri;
        }
    }

    server {
        listen 443 ssl http2;
        server_name ${var.domain_name} www.${var.domain_name};
        client_max_body_size 100M;

        # SSL Certificate
        ssl_certificate     /etc/letsencrypt/live/${var.domain_name}/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/${var.domain_name}/privkey.pem;
        ssl_protocols       TLSv1.2 TLSv1.3;
        ssl_prefer_server_ciphers on;
        ssl_ciphers         HIGH:!aNULL:!MD5;

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

    # Set up Let's Encrypt SSL
    echo "Setting up Let's Encrypt certificates..."
    certbot certonly --standalone -d ${var.domain_name} -d www.${var.domain_name} \
      --non-interactive --agree-tos -m ${var.admin_email} \
      --pre-hook "systemctl stop nginx" \
      --post-hook "systemctl start nginx"

    # Set up auto-renewal
    echo "0 0,12 * * * root certbot renew --pre-hook 'systemctl stop nginx' --post-hook 'systemctl start nginx' --quiet" > /etc/cron.d/certbot-renewal

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

  # User data template - without TLS
  user_data_tls_disabled = <<-EOF
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

    # Configure Nginx with Basic Auth (HTTP only)
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
}

# ACM Certificate for HTTPS
resource "aws_acm_certificate" "cert" {
  count             = var.enable_domain_and_tls ? 1 : 0
  domain_name       = var.domain_name
  validation_method = "DNS"

  subject_alternative_names = [
    "*.${var.domain_name}"
  ]

  lifecycle {
    create_before_destroy = true
  }
}

# DNS validation records for ACM
resource "aws_route53_record" "cert_validation" {
  for_each = var.enable_domain_and_tls ? {
    for dvo in aws_acm_certificate.cert[0].domain_validation_options : dvo.domain_name => {
      name    = dvo.resource_record_name
      type    = dvo.resource_record_type
      record  = dvo.resource_record_value
    }
  } : {}

  zone_id = local.zone_id
  name    = each.value.name
  type    = each.value.type
  records = [each.value.record]
  ttl     = 60
}

# Certificate validation
resource "aws_acm_certificate_validation" "cert" {
  count                   = var.enable_domain_and_tls ? 1 : 0
  certificate_arn         = aws_acm_certificate.cert[0].arn
  validation_record_fqdns = [for record in aws_route53_record.cert_validation : record.fqdn]
}

# Route 53 A Record for the domain
resource "aws_route53_record" "www" {
  count   = var.enable_domain_and_tls ? 1 : 0
  zone_id = local.zone_id
  name    = var.domain_name
  type    = "A"
  ttl     = "300"
  records = [aws_instance.streamlit_server.public_ip]
}

# Route 53 A Record for www subdomain
resource "aws_route53_record" "www_subdomain" {
  count   = var.enable_domain_and_tls ? 1 : 0
  zone_id = local.zone_id
  name    = "www.${var.domain_name}"
  type    = "A"
  ttl     = "300"
  records = [aws_instance.streamlit_server.public_ip]
}

# EC2 Instance
resource "aws_instance" "streamlit_server" {
  ami                    = var.ami_id
  instance_type          = var.instance_type
  key_name               = var.key_name
  vpc_security_group_ids = [aws_security_group.streamlit_sg.id]
  iam_instance_profile   = aws_iam_instance_profile.ec2_profile.name

  # Install required software via user_data (conditional based on TLS enablement)
  user_data = var.enable_domain_and_tls ? local.user_data_tls_enabled : local.user_data_tls_disabled

  tags = {
    Name = "ncsoccer-streamlit-server"
  }
}