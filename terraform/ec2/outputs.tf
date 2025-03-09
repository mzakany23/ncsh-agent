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
  value       = var.domain_name
}

output "http_url" {
  description = "HTTP URL to access the application (redirects to HTTPS)"
  value       = "http://${var.domain_name}"
}

output "https_url" {
  description = "HTTPS URL to access the application"
  value       = "https://${var.domain_name}"
}

output "certificate_arn" {
  description = "ARN of the ACM certificate"
  value       = aws_acm_certificate.cert.arn
}

output "zone_id" {
  description = "Route 53 zone ID"
  value       = local.zone_id
}