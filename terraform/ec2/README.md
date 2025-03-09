# NC Soccer Hudson - Match Analysis Agent Deployment

This directory contains the Terraform configuration to deploy the NC Soccer Hudson - Match Analysis Agent to AWS EC2.

## Prerequisites

1. AWS CLI installed and configured with appropriate credentials
2. Terraform installed (version >= 1.0.0)
3. An SSH key pair created in AWS (default name: `ncsoccer-key`)
4. A domain name (either new or existing in Route 53)
5. S3 bucket with your application data

## Deployment Architecture

The deployment includes:

1. **EC2 Instance**: Amazon Linux 2 with t2.micro instance type (free tier eligible)
2. **Security Group**: Allows incoming traffic on ports 80 (HTTP), 443 (HTTPS), and 22 (SSH)
3. **Software Stack**:
   - Docker for containerization
   - Nginx as a reverse proxy with basic authentication and SSL/TLS
   - Application deployed as a Docker container
   - Let's Encrypt for SSL certificate management
4. **Data Management**:
   - AWS IAM Role with permissions to access S3 data
   - Automatic syncing of data from S3 to the application
5. **Domain & SSL**:
   - Route 53 for DNS management
   - Let's Encrypt certificates for HTTPS
   - Automatic certificate renewal

This architecture ensures compatibility across different environments and provides security through:
- Using Docker to encapsulate the application and its dependencies
- Ensuring Python version compatibility (Python 3.11 in the container)
- Simplifying installation of complex dependencies
- Enabling HTTPS with free, auto-renewing certificates
- IAM-restricted access to data sources

## Deployment Steps

### 1. Create `terraform.tfvars` file

Create a `terraform.tfvars` file with the required variables:

```hcl
# Your SSH key pair name in AWS
key_name = "ncsoccer-key"

# Password for Nginx basic authentication
basic_auth_password = "your-secure-password-here"

# Anthropic API key
anthropic_api_key = "your-anthropic-api-key-here"

# Domain configuration
domain_name = "example.com"
create_new_domain = false  # Set to true if you want Terraform to create the Route 53 zone
admin_email = "admin@example.com"

# S3 data configuration
s3_data_bucket = "your-data-bucket-name"
s3_data_path = "data"  # Path within the bucket
```

### 2. Initialize Terraform

```bash
terraform init
```

### 3. Deploy the Infrastructure

```bash
terraform apply
```

When prompted, type `yes` to confirm the deployment.

### 4. Access Your Application

After the deployment is complete, Terraform will output:
- The public IP address of your EC2 instance
- The public DNS name
- The HTTPS URL to access your application
- The domain name configured

Your application will be accessible at the provided HTTPS URL with basic authentication:
- Username: `ncsoccer`
- Password: The value you set for `basic_auth_password` in your `terraform.tfvars` file

## Domain Configuration Options

### Using an Existing Domain

If you already have a domain registered in Route 53:
1. Set `domain_name` to your domain (e.g., "example.com")
2. Set `create_new_domain` to `false`

### Creating a New Domain

If you want Terraform to create a new hosted zone:
1. Register your domain with a domain registrar
2. Set `domain_name` to your domain
3. Set `create_new_domain` to `true`
4. After deployment, update your domain's nameservers with your registrar using the NS records from the Route 53 hosted zone

## Data Syncing

The deployment includes automatic data syncing from the application's S3 bucket:

1. An IAM role is created with restricted permissions to access the S3 bucket `ncsh-app-data` and the path `data/parquet`
2. On container startup, the existing `make refresh-data` command is executed to fetch the data from S3
3. The Makefile is configured to download the parquet file from `s3://ncsh-app-data/data/parquet/data.parquet` to `analysis/data/sample.parquet`
4. The file is then copied to `data.parquet` for compatibility with the application

No additional configuration is needed for data syncing as the S3 bucket and path are hardcoded in the Makefile.

## SSL Certificate Management

SSL certificates are handled using Let's Encrypt:

1. During deployment, a certificate is automatically requested and validated
2. Nginx is configured to use the certificate for HTTPS
3. A cron job is set up to automatically renew the certificate before expiration
4. HTTP requests are automatically redirected to HTTPS

## Troubleshooting

If you encounter issues with the deployment, you can SSH into the instance:

```bash
ssh -i /path/to/ncsoccer-key.pem ec2-user@<public-ip-from-output>
```

Common troubleshooting steps:

1. Check Nginx status:
   ```bash
   sudo systemctl status nginx
   ```

2. Check Docker container status:
   ```bash
   sudo docker ps -a
   ```

3. View Docker container logs:
   ```bash
   sudo docker logs ncsoccer-ui
   ```

4. Check Nginx logs:
   ```bash
   sudo journalctl -u nginx
   ```

5. Check Let's Encrypt logs:
   ```bash
   sudo journalctl -u certbot
   ```

6. Check certificate status:
   ```bash
   sudo certbot certificates
   ```

7. Restart the Docker container:
   ```bash
   sudo docker restart ncsoccer-ui
   ```

8. Rebuild and restart the container if needed:
   ```bash
   cd /home/ec2-user/streamlit-app
   sudo docker build -t ncsoccer-ui -f ui/Dockerfile .
   sudo docker stop ncsoccer-ui
   sudo docker rm ncsoccer-ui
   sudo docker run -d --name ncsoccer-ui --restart unless-stopped \
     -p 8501:8501 \
     -e ANTHROPIC_API_KEY="your-api-key" \
     -e BASIC_AUTH_USERNAME=ncsoccer \
     -e BASIC_AUTH_PASSWORD="your-password" \
     -e S3_DATA_BUCKET="your-bucket" \
     -e S3_DATA_PATH="data" \
     ncsoccer-ui
   ```

## Customization

You can modify the following aspects of the deployment:

1. **Instance Type**: Change the `instance_type` parameter in `main.tf` if you need more resources.
2. **Region**: Modify the AWS region in the provider block in `main.tf`.
3. **Basic Auth Username**: Change the username in the htpasswd command and Docker run command.
4. **SSL Configuration**: Modify the SSL settings in the Nginx configuration in `main.tf`.
5. **S3 Data Path**: Change the S3 bucket and path in your `terraform.tfvars` file.

## Cleanup

To avoid incurring charges, remove the deployed resources when they are no longer needed:

```bash
terraform destroy
```

When prompted, type `yes` to confirm the destruction of resources.