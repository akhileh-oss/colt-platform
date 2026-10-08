output "primary_endpoint_address" {
  value = aws_elasticache_replication_group.this.primary_endpoint_address
}

output "port" {
  value = 6379
}

output "tls_enabled" {
  description = "Transit encryption is on; the deployed REDIS_URL must use the `rediss://` scheme, not `redis://`."
  value       = true
}
