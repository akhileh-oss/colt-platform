output "frontend_address" {
  description = "Internal DNS address the application services' TEMPORAL_ADDRESS should point at."
  value       = "temporal.${aws_service_discovery_private_dns_namespace.this.name}:7233"
}
