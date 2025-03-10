variable "key_name" {
  description = "The name of your SSH key pair in AWS"
  type        = string
  default     = "ncsoccer-key"
}

variable "basic_auth_password" {
  description = "Password for basic authentication"
  type        = string
  sensitive   = true
}

variable "anthropic_api_key" {
  description = "API key for Anthropic Claude"
  type        = string
  sensitive   = true
}

variable "instance_type" {
  description = "EC2 instance type"
  type        = string
  default     = "t2.micro"
}

variable "ami_id" {
  description = "AMI ID to use for the EC2 instance (default: latest Amazon Linux 2)"
  type        = string
  default     = "ami-09dc1ba68d413c979" # Amazon Linux 2 AMI (HVM) - Kernel 5.10, SSD Volume Type
}

variable "enable_domain_and_tls" {
  description = "Whether to enable domain name and TLS support"
  type        = bool
  default     = false
}

variable "domain_name" {
  description = "Domain name for the application"
  type        = string
  default     = ""
}

variable "create_new_domain" {
  description = "Whether to create a new Route 53 hosted zone (if false, uses existing zone)"
  type        = bool
  default     = false
}

variable "route53_zone_id" {
  description = "Existing Route 53 zone ID to use (optional, used if multiple zones exist for domain)"
  type        = string
  default     = ""
}

variable "admin_email" {
  description = "Email address for Let's Encrypt certificate notifications"
  type        = string
  default     = ""
}