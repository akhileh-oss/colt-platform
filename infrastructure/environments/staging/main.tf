/*
 * Staging: the smallest real shape of production (single-AZ NAT, no Multi-AZ RDS/Redis, one
 * task per service) — cheap enough to run continuously, but every module, every IAM policy, and
 * every alarm is identical in kind to production's, so a staging soak (Milestone 27) actually
 * exercises the real topology, not a simplified stand-in for it.
 */

module "environment" {
  source = "../../terraform/environment"

  environment = "staging"
  aws_region  = var.aws_region
  azs         = var.azs

  domain_name     = var.domain_name
  create_dns_zone = true
  alert_email     = var.alert_email

  single_nat_gateway = true
  database_multi_az  = false
  cache_multi_az     = false

  object_storage_bucket_name = var.object_storage_bucket_name

  api_image    = var.api_image
  web_image    = var.web_image
  worker_image = var.worker_image
}
