variable "key_name" {
  description = "The name of the SSH key pair to use for EC2 instance"
  type        = string
  default     = "ncsoccer-key"
}

variable "basic_auth_password" {
  description = "Password for Nginx basic authentication"
  type        = string
  sensitive   = true
}

variable "anthropic_api_key" {
  description = "API key for Anthropic Claude"
  type        = string
  sensitive   = true
}