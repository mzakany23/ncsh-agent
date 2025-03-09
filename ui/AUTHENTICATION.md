# NC Soccer Hudson - Match Analysis Agent Authentication

This document describes how to use the authentication setup for the NC Soccer Hudson - Match Analysis Agent.

## Local Testing with Authentication

The application now includes Nginx with Basic Authentication to protect access to the Streamlit app.

### Running Locally with Docker

1. Create a `.env` file in the `ui` directory with your credentials:

```
ANTHROPIC_API_KEY=your_api_key
BASIC_AUTH_USERNAME=your_preferred_username
BASIC_AUTH_PASSWORD=your_secure_password
```

2. Start the application with Docker Compose:

```bash
cd ui
docker-compose up --build
```

3. Access the application:
   - Authenticated version: http://localhost:8080 (will prompt for username/password)
   - Direct access (for debugging): http://localhost:8503

### Default Credentials

If you don't specify credentials in your `.env` file, the system will use these defaults:
- Username: `ncsoccer`
- Password: `password`

**Important:** Always change the default password in production!

## Deployment to AWS

For production deployment, the application can be deployed to AWS EC2 using Terraform. See the `terraform/ec2` directory for the deployment configuration.

### Prerequisites for AWS Deployment

1. AWS account and CLI configured
2. Terraform installed
3. SSH key pair created in AWS

### Deployment Steps

1. Navigate to the Terraform directory:

```bash
cd terraform/ec2
```

2. Initialize Terraform:

```bash
terraform init
```

3. Create a `terraform.tfvars` file with your variable values:

```
basic_auth_password = "your_secure_password"
anthropic_api_key   = "your_api_key"
key_name            = "your_aws_key_pair_name"
```

4. Apply the Terraform configuration:

```bash
terraform apply
```

5. Terraform will output the URL to access your deployed application.

## Security Considerations

- In production, restrict SSH access to specific IP addresses
- Use HTTPS with a valid SSL certificate
- Use a strong password for Basic Authentication
- Consider implementing more robust authentication for production environments