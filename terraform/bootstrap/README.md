# Terraform Backend Setup

This directory contains the Terraform configuration to set up the infrastructure needed for the Terraform remote backend:

1. An S3 bucket for storing Terraform state files
2. A DynamoDB table for state locking
3. Appropriate security configurations and encryption
4. Optional: Route 53 hosted zone for domains

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

3. If you're using a domain name, create a terraform.tfvars file:

```bash
echo 'domain_name = "yourdomain.com"' > terraform.tfvars
```

4. Apply the configuration:

```bash
terraform apply
```

5. Note the outputs, which will include:
   - The S3 bucket name
   - The DynamoDB table name
   - The Terraform backend configuration to copy into other Terraform configurations
   - If a domain was provided: Route 53 zone ID and nameservers

6. If using a domain, update your domain registrar (like Namecheap) with the nameservers provided in the output.

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

## Using the Domain in the EC2 Configuration

When deploying the EC2 instance with the domain created in this bootstrap:

1. In the EC2 terraform.tfvars, set:
```
enable_domain_and_tls = true
domain_name = "yourdomain.com"  # Same as used in bootstrap
create_new_domain = false  # Important: set to false since domain is created in bootstrap
```

## Security Considerations

The S3 bucket created by this configuration:
- Blocks all public access
- Enables server-side encryption
- Enables versioning to protect against accidental deletion
- Uses a randomly generated suffix to ensure a unique name

The DynamoDB table uses on-demand pricing to avoid unnecessary costs.

The Route 53 hosted zone (if created) will be configured for your domain and will generate nameservers that you need to configure with your domain registrar.