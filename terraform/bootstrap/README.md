# Terraform Backend Setup

This directory contains the Terraform configuration to set up the infrastructure needed for the Terraform remote backend:

1. An S3 bucket for storing Terraform state files
2. A DynamoDB table for state locking
3. Appropriate security configurations and encryption

## One-time Setup Process

These resources need to be created before the rest of the Terraform configurations can use the remote backend.

### Prerequisites

- AWS CLI installed and configured with appropriate credentials
- Terraform installed (version >= 1.0.0)

### Steps

1. Navigate to this directory:

```bash
cd terraform/bootstrap
```

2. Initialize Terraform:

```bash
terraform init
```

3. Apply the configuration:

```bash
terraform apply
```

4. Note the outputs, which will include:
   - The S3 bucket name
   - The DynamoDB table name
   - The Terraform backend configuration to copy into other Terraform configurations

## Using the Backend in Other Terraform Configurations

After running this bootstrap configuration, copy the backend configuration from the output into your other Terraform files. It should look something like this:

```hcl
terraform {
  backend "s3" {
    bucket         = "ncsoccer-tfstate-abc123def"
    key            = "terraform.tfstate"
    region         = "us-east-2"
    dynamodb_table = "ncsoccer-terraform-locks"
    encrypt        = true
  }
}
```

### Multiple State Files

For multiple Terraform configurations, use a different `key` value for each:

```hcl
terraform {
  backend "s3" {
    bucket         = "ncsoccer-tfstate-abc123def"
    key            = "oidc/terraform.tfstate"  # Different path for different configurations
    region         = "us-east-2"
    dynamodb_table = "ncsoccer-terraform-locks"
    encrypt        = true
  }
}
```

## Security Considerations

The S3 bucket created by this configuration:
- Blocks all public access
- Enables server-side encryption
- Enables versioning to protect against accidental deletion
- Uses a randomly generated suffix to ensure a unique name

The DynamoDB table uses on-demand pricing to avoid unnecessary costs.