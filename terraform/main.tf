terraform {
  backend "s3" {
    bucket         = "ncsoccer-tfstate-siu66w32"
    key            = "oidc/terraform.tfstate"
    region         = "us-east-2"
    dynamodb_table = "ncsoccer-terraform-locks"
    encrypt        = true
  }
}

provider "aws" {
  region = var.region
}

# Configure the GitHub OIDC provider
module "github_oidc" {
  source             = "./modules/github-oidc"
  github_repository  = var.github_repository
  oidc_role_name     = var.oidc_role_name
  create_oidc_provider = false  # Set to false since the provider already exists
}

# Output the role ARN for GitHub Actions
output "github_actions_role_arn" {
  value       = module.github_oidc.role_arn
  description = "ARN of the IAM role for GitHub Actions"
}