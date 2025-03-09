terraform {
  # This will be filled in after running the bootstrap process
  # backend "s3" {
  #   bucket         = "BUCKET_NAME_FROM_BOOTSTRAP"
  #   key            = "oidc/terraform.tfstate"
  #   region         = "us-east-2"
  #   dynamodb_table = "DYNAMODB_TABLE_FROM_BOOTSTRAP"
  #   encrypt        = true
  # }
}

provider "aws" {
  region = var.region
}

# Configure the GitHub OIDC provider
module "github_oidc" {
  source            = "./modules/github-oidc"
  github_repository = var.github_repository
  oidc_role_name    = var.oidc_role_name
}

# Output the role ARN for GitHub Actions
output "github_actions_role_arn" {
  value       = module.github_oidc.role_arn
  description = "ARN of the IAM role for GitHub Actions"
}