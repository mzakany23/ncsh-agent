output "public_ip" {
  description = "Public IP address of the EC2 instance"
  value       = aws_instance.streamlit_server.public_ip
}

output "public_dns" {
  description = "Public DNS of the EC2 instance"
  value       = aws_instance.streamlit_server.public_dns
}

output "url" {
  description = "URL to access the Streamlit application"
  value       = "http://${aws_instance.streamlit_server.public_dns}"
}