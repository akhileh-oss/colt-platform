/*
 * Production: the same `environment` module staging uses, with every single-point-of-failure
 * knob staging leaves off turned on — Multi-AZ RDS, Multi-AZ Redis with automatic failover, one
 * NAT gateway per AZ, and a larger, multi-task shape per service.
 */

module "environment" {
  source = "../../terraform/environment"

  environment = "production"
  aws_region  = var.aws_region
  azs         = var.azs

  domain_name     = var.domain_name
  create_dns_zone = true
  alert_email     = var.alert_email

  single_nat_gateway = false
  database_multi_az  = true
  cache_multi_az     = true

  database_instance_class        = "db.r6g.large"
  database_backup_retention_days = 30
  cache_node_type                = "cache.r6g.large"
  backup_retention_days          = 90

  object_storage_bucket_name = var.object_storage_bucket_name

  api_image      = var.api_image
  web_image      = var.web_image
  worker_image   = var.worker_image
  service_sizing = var.service_sizing
}
