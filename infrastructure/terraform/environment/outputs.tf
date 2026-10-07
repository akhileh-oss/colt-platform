output "alb_dns_name" {
  value = module.compute.alb_dns_name
}

output "app_url" {
  value = "https://${var.domain_name}"
}

output "database_address" {
  value = module.database.address
}

output "cache_endpoint" {
  value = module.cache.primary_endpoint_address
}

output "object_storage_bucket_name" {
  value = module.object_storage.bucket_name
}

output "temporal_frontend_address" {
  value = module.temporal.frontend_address
}

output "dashboard_name" {
  value = module.observability.dashboard_name
}

output "nameservers" {
  description = "Only meaningful when `create_dns_zone = true`: the NS records to delegate from the parent zone."
  value       = var.create_dns_zone ? module.dns_tls.zone_id : null
}
