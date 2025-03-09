provider "aws" {
  region = "us-east-2"
}

# Random string to make bucket name unique
resource "random_string" "suffix" {
  length  = 8
  special = false
  upper   = false
}

# S3 bucket for Terraform state
resource "aws_s3_bucket" "terraform_state" {
  bucket = "ncsoccer-tfstate-${random_string.suffix.result}"

  lifecycle {
    prevent_destroy = true
  }

  tags = {
    Name        = "NC Soccer Terraform State"
    Environment = "All"
    ManagedBy   = "Terraform"
  }
}

# Enable bucket versioning
resource "aws_s3_bucket_versioning" "terraform_state_versioning" {
  bucket = aws_s3_bucket.terraform_state.id

  versioning_configuration {
    status = "Enabled"
  }
}

# Enable server-side encryption by default
resource "aws_s3_bucket_server_side_encryption_configuration" "terraform_state_encryption" {
  bucket = aws_s3_bucket.terraform_state.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Block public access to the bucket
resource "aws_s3_bucket_public_access_block" "terraform_state_public_access" {
  bucket = aws_s3_bucket.terraform_state.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# DynamoDB table for state locking
resource "aws_dynamodb_table" "terraform_locks" {
  name         = "ncsoccer-terraform-locks"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"

  attribute {
    name = "LockID"
    type = "S"
  }

  tags = {
    Name        = "NC Soccer Terraform Locks"
    Environment = "All"
    ManagedBy   = "Terraform"
  }
}

# Outputs
output "s3_bucket_name" {
  value       = aws_s3_bucket.terraform_state.bucket
  description = "The name of the S3 bucket for Terraform state"
}

output "dynamodb_table_name" {
  value       = aws_dynamodb_table.terraform_locks.name
  description = "The name of the DynamoDB table for Terraform state locking"
}

output "terraform_backend_config" {
  value = <<EOF

# Add this to your Terraform configurations:
terraform {
  backend "s3" {
    bucket         = "${aws_s3_bucket.terraform_state.bucket}"
    key            = "terraform.tfstate"
    region         = "us-east-2"
    dynamodb_table = "${aws_dynamodb_table.terraform_locks.name}"
    encrypt        = true
  }
}
EOF
  description = "Backend configuration for Terraform"
}