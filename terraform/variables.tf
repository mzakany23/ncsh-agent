variable "region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "us-east-2"
}

variable "github_repository" {
  description = "GitHub repository (format: organization/repository)"
  type        = string
  default     = "michaelzakany/ncsoccer-agent"  # Update this with your actual repository
}

variable "oidc_role_name" {
  description = "Name for the IAM role that will be created for GitHub Actions"
  type        = string
  default     = "github-actions-ncsoccer-role"
}