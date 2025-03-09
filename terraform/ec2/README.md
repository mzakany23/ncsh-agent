# NC Soccer Hudson - Match Analysis Agent Deployment

This directory contains the Terraform configuration to deploy the NC Soccer Hudson - Match Analysis Agent to AWS EC2.

## Prerequisites

1. AWS CLI installed and configured with appropriate credentials
2. Terraform installed (version >= 1.0.0)
3. An SSH key pair created in AWS (default name: `ncsoccer-key`)

## Deployment Architecture

The deployment includes:

1. **EC2 Instance**: Amazon Linux 2 with t2.micro instance type (free tier eligible)
2. **Security Group**: Allows incoming traffic on ports 80 (HTTP), 443 (HTTPS), and 22 (SSH)
3. **Software Stack**:
   - Docker for containerization
   - Nginx as a reverse proxy with basic authentication
   - Application deployed as a Docker container

This architecture ensures compatibility across different environments by:
- Using Docker to encapsulate the application and its dependencies
- Ensuring Python version compatibility (Python 3.11 in the container)
- Simplifying installation of complex dependencies

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
- The URL to access your application

Your application will be accessible at the provided URL with basic authentication:
- Username: `ncsoccer`
- Password: The value you set for `basic_auth_password` in your `terraform.tfvars` file

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

5. Restart the Docker container:
   ```bash
   sudo docker restart ncsoccer-ui
   ```

6. Rebuild and restart the container if needed:
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
     ncsoccer-ui
   ```

## Customization

You can modify the following aspects of the deployment:

1. **Instance Type**: Change the `instance_type` parameter in `main.tf` if you need more resources.
2. **Region**: Modify the AWS region in the provider block in `main.tf`.
3. **Basic Auth Username**: Change the username in the htpasswd command and Docker run command.

## Cleanup

To avoid incurring charges, remove the deployed resources when they are no longer needed:

```bash
terraform destroy
```

When prompted, type `yes` to confirm the destruction of resources.