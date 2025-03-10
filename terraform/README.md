# AWS Infrastructure and GitHub OIDC Setup

This directory contains Terraform configurations for:

1. Setting up the Terraform backend with S3 and DynamoDB
2. Setting up GitHub OIDC authentication with AWS
3. Deploying the NC Soccer Hudson - Match Analysis Agent to AWS EC2

## Initial Setup

The deployment process has three phases:

### Phase 1: Set up Terraform Backend Infrastructure

Before you can use the OIDC authentication and deploy resources, you need to set up the Terraform backend infrastructure:

1. Follow the instructions in the [bootstrap README](./bootstrap/README.md) to create the S3 bucket and DynamoDB table
2. After the bootstrap process, update the backend configurations in `main.tf` and `ec2/main.tf` with the values from the bootstrap output

### Phase 2: Set up GitHub OIDC Authentication

Once the backend is set up:

1. Create an IAM user with appropriate permissions in AWS
2. Use these credentials to manually apply the Terraform configuration once
3. After this initial setup, GitHub Actions can use OIDC for authentication

```bash
# Configure AWS CLI with your access keys
aws configure

# Initialize Terraform
cd terraform
terraform init

# Apply the Terraform configuration
terraform apply
```

When prompted, enter your GitHub repository in the format `organization/repository` (e.g., `michaelzakany/ncsoccer-agent`).

### Phase 3: Configure GitHub Secrets

After applying the Terraform configuration, you'll get an output with the IAM role ARN.

Add the following secret to your GitHub repository:
- `AWS_SETUP_ROLE_ARN`: The ARN of the role you created manually (this is a temporary requirement)

Once the OIDC provider is fully set up, you only need these secrets:
- `BASIC_AUTH_PASSWORD`: Password for Nginx basic authentication
- `ANTHROPIC_API_KEY`: API key for Anthropic Claude
- `AWS_KEY_NAME`: Name of your SSH key pair in AWS
- `AWS_SSH_KEY`: Private SSH key for accessing the EC2 instance

## OIDC Authentication Flow

The setup uses OpenID Connect (OIDC) to allow GitHub Actions to authenticate with AWS without storing long-lived AWS credentials as GitHub secrets. Here's how it works:

1. When a GitHub Actions workflow runs, it can request a short-lived token from GitHub's OIDC provider
2. AWS is configured to trust tokens from GitHub's OIDC provider for specific repositories
3. GitHub Actions can exchange this token for temporary AWS credentials by assuming an IAM role
4. These temporary credentials are used to deploy resources in AWS

## Deployment Architecture

The deployment consists of:

- An EC2 instance running the Streamlit application
- Nginx for basic authentication and serving the application
- Security group for controlling access to the instance

## Modifying the Infrastructure

If you need to modify the infrastructure:

1. Update the relevant Terraform files
2. Commit and push your changes
3. The GitHub Actions workflow will automatically apply the changes

## Security Considerations

- The OIDC integration restricts access to GitHub workflows running in your specific repository
- For production use, consider restricting the IAM role permissions further
- Regularly rotate the Nginx basic auth password and SSH key
- The Terraform state is stored securely in an S3 bucket with encryption and versioning
- The DynamoDB table prevents concurrent modifications to the infrastructure