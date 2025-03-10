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
  count        = var.enable_domain_and_tls && !var.create_new_domain ? 1 : 0
  name         = var.domain_name
  private_zone = false
  zone_id      = var.route53_zone_id != "" ? var.route53_zone_id : null
}

locals {
  zone_id = var.enable_domain_and_tls ? (var.create_new_domain ? aws_route53_zone.main[0].zone_id : data.aws_route53_zone.existing[0].zone_id) : ""

  # User data template - with TLS enabled
  user_data_tls_enabled = <<-EOF
    #!/bin/bash
    set -e

    # Enable debug output
    exec > >(tee /var/log/user-data.log|logger -t user-data ) 2>&1
    echo "===== Starting deployment setup: $(date) ====="

    # Update system packages
    echo "Updating system packages..."
    yum update -y

    # Install basic HTTP server first to verify connectivity
    echo "Installing Apache..."
    yum install -y httpd

    # Create a simple test page
    echo "<html><body><h1>NC Soccer Hudson Test Page</h1><p>Site is initializing... Please wait while we set up the Streamlit application (5-10 minutes).</p></body></html>" > /var/www/html/index.html

    # Start Apache to confirm connectivity
    echo "Starting Apache..."
    systemctl enable httpd
    systemctl start httpd

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

    # Configure Nginx
    echo "Installing and configuring Nginx..."
    amazon-linux-extras install -y nginx1

    # Create self-signed certificates for immediate HTTPS availability
    echo "Creating self-signed certificates for immediate HTTPS..."
    mkdir -p /etc/ssl/private
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
      -keyout /etc/ssl/private/nginx-selfsigned.key \
      -out /etc/ssl/certs/nginx-selfsigned.crt \
      -subj "/C=US/ST=Ohio/L=Hudson/O=NC Soccer/CN=ncsh.${var.domain_name}"

    # Configure Nginx for HTTP and HTTPS with self-signed certificate
    cat > /etc/nginx/conf.d/streamlit.conf << NGINXCONF
    server {
        listen 80;
        server_name ncsh.${var.domain_name};
        client_max_body_size 100M;

        location / {
            auth_basic "NC Soccer Hudson - Match Analysis Agent";
            auth_basic_user_file /etc/nginx/.htpasswd;
            proxy_pass http://localhost:8501;
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

    server {
        listen 443 ssl;
        server_name ncsh.${var.domain_name};
        client_max_body_size 100M;

        ssl_certificate /etc/ssl/certs/nginx-selfsigned.crt;
        ssl_certificate_key /etc/ssl/private/nginx-selfsigned.key;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_prefer_server_ciphers on;
        ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384;

        location / {
            auth_basic "NC Soccer Hudson - Match Analysis Agent";
            auth_basic_user_file /etc/nginx/.htpasswd;
            proxy_pass http://localhost:8501;
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

    # Stop Apache as we'll use Nginx instead
    echo "Stopping Apache and starting Nginx..."
    systemctl stop httpd
    systemctl disable httpd

    # Start and enable Nginx
    systemctl enable nginx
    systemctl start nginx

    # Test Nginx configuration
    echo "Testing Nginx configuration..."
    nginx -t

    # Testing HTTPS setup
    echo "Testing HTTPS setup..."
    curl -k https://localhost -I

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

    # Install certbot for Let's Encrypt certificates (after HTTPS is already working with self-signed)
    echo "Installing certbot for Let's Encrypt..."
    amazon-linux-extras install -y epel
    yum install -y certbot python3-certbot-nginx

    # Obtain Let's Encrypt certificates (will replace self-signed when ready)
    echo "Obtaining Let's Encrypt certificates (in background)..."
    nohup certbot --nginx -d ncsh.${var.domain_name} --non-interactive --agree-tos -m ${var.admin_email} --redirect --verbose > /var/log/certbot.log 2>&1 &

    # Set up automatic renewal
    echo "Setting up automatic certificate renewal..."
    echo "0 3 * * * root certbot renew --quiet --deploy-hook 'systemctl reload nginx'" > /etc/cron.d/certbot

    echo "===== Deployment setup finished: $(date) ====="
    echo "HTTPS is available immediately with self-signed certificate."
    echo "Let's Encrypt certificate setup is running in the background."
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
    "*.${var.domain_name}",
    "ncsh.${var.domain_name}",
    "ncsh.dev.${var.domain_name}"
  ]

  lifecycle {
    create_before_destroy = true
  }
}

# ACM Certificate validation records
resource "aws_route53_record" "cert_validation" {
  for_each = var.enable_domain_and_tls ? {
    for dvo in aws_acm_certificate.cert[0].domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      record = dvo.resource_record_value
      type   = dvo.resource_record_type
    }
  } : {}

  allow_overwrite = true
  name            = each.value.name
  records         = [each.value.record]
  ttl             = 60
  type            = each.value.type
  zone_id         = local.zone_id
}

# Certificate validation
resource "aws_acm_certificate_validation" "cert" {
  count                   = var.enable_domain_and_tls ? 1 : 0
  certificate_arn         = aws_acm_certificate.cert[0].arn
  validation_record_fqdns = [for record in aws_route53_record.cert_validation : record.fqdn]
}

# Route 53 A Record for the domain
resource "aws_route53_record" "www" {
  count           = var.enable_domain_and_tls ? 1 : 0
  zone_id         = local.zone_id
  name            = var.domain_name
  type            = "A"
  ttl             = "300"
  records         = [aws_instance.streamlit_server.public_ip]
  allow_overwrite = true
}

# Route 53 A Record for www subdomain
resource "aws_route53_record" "www_subdomain" {
  count           = var.enable_domain_and_tls ? 1 : 0
  zone_id         = local.zone_id
  name            = "www.${var.domain_name}"
  type            = "A"
  ttl             = "300"
  records         = [aws_instance.streamlit_server.public_ip]
  allow_overwrite = true
}

# Route 53 A Record for ncsh subdomain
resource "aws_route53_record" "ncsh_subdomain" {
  count           = var.enable_domain_and_tls ? 1 : 0
  zone_id         = local.zone_id
  name            = "ncsh.${var.domain_name}"
  type            = "A"
  ttl             = "300"
  records         = [aws_instance.streamlit_server.public_ip]
  allow_overwrite = true
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