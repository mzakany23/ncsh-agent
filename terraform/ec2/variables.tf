variable "key_name" {
  description = "The name of the SSH key pair to use for EC2 instance. Must be created in AWS Console first."
  type        = string
  default     = "ncsoccer-key"
}

variable "basic_auth_password" {
  description = "Password for Nginx basic authentication. This will be used with username 'ncsoccer'."
  type        = string
  sensitive   = true
}

variable "anthropic_api_key" {
  description = "API key for Anthropic Claude. Required for the Streamlit application to function."
  type        = string
  sensitive   = true
}

variable "instance_type" {
  description = "EC2 instance type to use. Default is t2.micro (free tier eligible)."
  type        = string
  default     = "t2.micro"
}

variable "ami_id" {
  description = "AMI ID to use. If not specified, defaults to the latest Amazon Linux 2 AMI."
  type        = string
  default     = "ami-09dc1ba68d413c979"  # Amazon Linux 2 in us-east-2 (Ohio)
}

variable "domain_name" {
  description = "Domain name for the application (e.g., example.com)"
  type        = string
}

variable "create_new_domain" {
  description = "Whether to create a new Route 53 hosted zone or use an existing one"
  type        = bool
  default     = false
}

variable "admin_email" {
  description = "Email address for Let's Encrypt certificate notifications"
  type        = string
}

variable "s3_data_bucket" {
  description = "S3 bucket name containing the application data"
  type        = string
}

variable "s3_data_path" {
  description = "Path within the S3 bucket to the application data"
  type        = string
  default     = "data"
}