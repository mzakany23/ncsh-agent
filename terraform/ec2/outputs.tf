output "public_ip" {
  description = "Public IP address of the EC2 instance"
  value       = aws_instance.streamlit_server.public_ip
}

output "public_dns" {
  description = "Public DNS of the EC2 instance"
  value       = aws_instance.streamlit_server.public_dns
}

output "domain" {
  description = "Domain name of the application"
  value       = var.enable_domain_and_tls ? var.domain_name : null
}

output "http_url" {
  description = "HTTP URL to access the application"
  value       = "http://${aws_instance.streamlit_server.public_ip}"
}

output "https_url" {
  description = "HTTPS URL to access the application (if TLS enabled)"
  value       = var.enable_domain_and_tls ? "https://${var.domain_name}" : null
}

output "ncsh_url" {
  description = "HTTPS URL for the ncsh subdomain (if TLS enabled)"
  value       = var.enable_domain_and_tls ? "https://ncsh.${var.domain_name}" : null
}

output "certificate_arn" {
  description = "ARN of the ACM certificate (if TLS enabled)"
  value       = var.enable_domain_and_tls ? aws_acm_certificate.cert[0].arn : null
}

output "zone_id" {
  description = "Route 53 zone ID (if TLS enabled)"
  value       = var.enable_domain_and_tls ? local.zone_id : null
}