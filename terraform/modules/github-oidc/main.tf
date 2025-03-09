variable "github_repository" {
  type        = string
  description = "GitHub repository (format: organization/repository)"
}

variable "oidc_role_name" {
  type        = string
  description = "Name for the IAM role that will be created"
  default     = "github-actions-oidc-role"
}

# Create the OIDC Provider in AWS
resource "aws_iam_openid_connect_provider" "github_actions" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"]
}

# Create an IAM role that GitHub Actions can assume
resource "aws_iam_role" "github_actions" {
  name = var.oidc_role_name

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = aws_iam_openid_connect_provider.github_actions.arn
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
          }
          StringLike = {
            "token.actions.githubusercontent.com:sub": "repo:${var.github_repository}:*"
          }
        }
      }
    ]
  })
}

# Attach policies to the role
resource "aws_iam_role_policy_attachment" "ec2_full_access" {
  role       = aws_iam_role.github_actions.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2FullAccess"
}

resource "aws_iam_role_policy_attachment" "iam_full_access" {
  role       = aws_iam_role.github_actions.name
  policy_arn = "arn:aws:iam::aws:policy/IAMFullAccess"
}

resource "aws_iam_role_policy_attachment" "vpc_full_access" {
  role       = aws_iam_role.github_actions.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonVPCFullAccess"
}

output "role_arn" {
  value       = aws_iam_role.github_actions.arn
  description = "ARN of the IAM role for GitHub Actions"
}