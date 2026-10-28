/*
 * Oracle Cloud "Always Free" — a $0/month alternative to `environments/staging` and
 * `environments/production` (both AWS, Milestone 25), for anyone who cannot carry AWS's
 * recurring NAT Gateway / ALB / Fargate costs. See docs/operations/ORACLE_FREE_TIER_DEPLOYMENT.md
 * for the full write-up of what's actually free here, what it costs in resilience compared to
 * the AWS environments, and the one-time account setup this doesn't automate.
 *
 * Randomly generated with no special characters: this environment has no managed secrets
 * service to store them in (OCI's Always Free tier has no equivalent of AWS Secrets Manager),
 * so these end up verbatim in a shell heredoc inside cloud-init — a password containing `$`,
 * backtick, or a quote character risks breaking that heredoc on the instance, not just being
 * awkward to type.
 */

resource "random_password" "postgres" {
  length  = 32
  special = false
}

resource "random_password" "redis" {
  length  = 32
  special = false
}

resource "random_password" "minio" {
  length  = 32
  special = false
}

resource "random_password" "keycloak_admin" {
  length  = 32
  special = false
}

module "network" {
  source = "../../terraform/oracle/modules/network"

  compartment_id   = var.compartment_id
  name_prefix      = var.name_prefix
  ssh_allowed_cidr = var.ssh_allowed_cidr
}

module "compute" {
  source = "../../terraform/oracle/modules/compute"

  compartment_id = var.compartment_id
  name_prefix    = var.name_prefix
  subnet_id      = module.network.public_subnet_id
  nsg_id         = module.network.instance_nsg_id

  ssh_public_key = var.ssh_public_key
  domain_name    = var.domain_name

  ocpus                   = var.ocpus
  memory_in_gbs           = var.memory_in_gbs
  boot_volume_size_in_gbs = var.boot_volume_size_in_gbs
  data_volume_size_in_gbs = var.data_volume_size_in_gbs
  backup_retention_days   = var.backup_retention_days

  api_image    = var.api_image
  web_image    = var.web_image
  worker_image = var.worker_image

  postgres_password       = random_password.postgres.result
  redis_password          = random_password.redis.result
  minio_root_user         = "colt-minio"
  minio_root_password     = random_password.minio.result
  keycloak_admin_password = random_password.keycloak_admin.result

  extra_env = var.extra_env

  tags = var.tags
}
