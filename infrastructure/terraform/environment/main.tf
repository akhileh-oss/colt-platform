/*
 * Composes every leaf module into one environment (staging or production). Called from
 * `infrastructure/environments/staging/main.tf` and `.../production/main.tf` — each its own
 * Terraform root (its own backend, its own provider configuration), both instantiating this
 * same module so staging and production can never silently drift in how the pieces wire
 * together, only in the variable values each one passes.
 */

locals {
  name_prefix = "colt-${var.environment}"
  tags = merge(var.tags, {
    Environment = var.environment
    ManagedBy   = "terraform"
    Project     = "colt"
  })
}

module "networking" {
  source = "../modules/networking"

  name_prefix        = local.name_prefix
  vpc_cidr           = var.vpc_cidr
  azs                = var.azs
  single_nat_gateway = var.single_nat_gateway
  tags               = local.tags
}

module "database" {
  source = "../modules/database"

  name_prefix              = local.name_prefix
  private_subnet_ids       = module.networking.private_subnet_ids
  security_group_id        = module.networking.database_security_group_id
  instance_class           = var.database_instance_class
  allocated_storage_gb     = var.database_allocated_storage_gb
  max_allocated_storage_gb = var.database_max_allocated_storage_gb
  multi_az                 = var.database_multi_az
  backup_retention_days    = var.database_backup_retention_days
  tags                     = local.tags
}

module "cache" {
  source = "../modules/cache"

  name_prefix        = local.name_prefix
  private_subnet_ids = module.networking.private_subnet_ids
  security_group_id  = module.networking.cache_security_group_id
  node_type          = var.cache_node_type
  multi_az           = var.cache_multi_az
  tags               = local.tags
}

module "object_storage" {
  source = "../modules/object_storage"

  name_prefix = local.name_prefix
  bucket_name = var.object_storage_bucket_name
  tags        = local.tags
}

module "secrets" {
  source = "../modules/secrets"

  name_prefix  = local.name_prefix
  secret_names = var.application_secret_names
  tags         = local.tags
}

module "dns_tls" {
  source = "../modules/dns_tls"

  domain_name = var.domain_name
  create_zone = var.create_dns_zone
  tags        = local.tags
}

module "compute" {
  source = "../modules/compute"

  name_prefix                     = local.name_prefix
  vpc_id                          = module.networking.vpc_id
  public_subnet_ids               = module.networking.public_subnet_ids
  private_subnet_ids              = module.networking.private_subnet_ids
  alb_security_group_id           = module.networking.alb_security_group_id
  app_security_group_id           = module.networking.app_security_group_id
  certificate_arn                 = module.dns_tls.certificate_arn
  database_credentials_secret_arn = module.database.credentials_secret_arn
  application_secret_arns         = module.secrets.secret_arns
  object_storage_bucket_arn       = module.object_storage.bucket_arn
  tags                            = local.tags

  services = {
    api = {
      image             = var.api_image
      cpu               = var.service_sizing["api"].cpu
      memory            = var.service_sizing["api"].memory
      port              = 8000
      desired_count     = var.service_sizing["api"].desired_count
      public            = true
      path_pattern      = "/api/*"
      health_check_path = "/live"
      environment = [
        { name = "TEMPORAL_ADDRESS", value = module.temporal.frontend_address },
        { name = "OBJECT_STORAGE_BUCKET", value = module.object_storage.bucket_name },
      ]
    }
    web = {
      image             = var.web_image
      cpu               = var.service_sizing["web"].cpu
      memory            = var.service_sizing["web"].memory
      port              = 3000
      desired_count     = var.service_sizing["web"].desired_count
      public            = true
      path_pattern      = "/*"
      health_check_path = "/"
      environment       = []
    }
    worker = {
      image             = var.worker_image
      cpu               = var.service_sizing["worker"].cpu
      memory            = var.service_sizing["worker"].memory
      port              = 8001
      desired_count     = var.service_sizing["worker"].desired_count
      public            = false
      health_check_path = "/live"
      environment = [
        { name = "TEMPORAL_ADDRESS", value = module.temporal.frontend_address },
        { name = "OBJECT_STORAGE_BUCKET", value = module.object_storage.bucket_name },
      ]
    }
  }
}

module "temporal" {
  source = "../modules/temporal"

  name_prefix                     = local.name_prefix
  vpc_id                          = module.networking.vpc_id
  cluster_arn                     = module.compute.cluster_arn
  private_subnet_ids              = module.networking.private_subnet_ids
  app_security_group_id           = module.networking.app_security_group_id
  execution_role_arn              = module.compute.execution_role_arn
  task_role_arn                   = module.compute.task_role_arn
  database_host                   = module.database.address
  database_port                   = module.database.port
  database_credentials_secret_arn = module.database.credentials_secret_arn
  tags                            = local.tags
}

module "observability" {
  source = "../modules/observability"

  name_prefix          = local.name_prefix
  database_instance_id = module.database.instance_id
  alb_arn_suffix       = module.compute.alb_arn_suffix
  ecs_cluster_name     = module.compute.cluster_name
}

module "alerting" {
  source = "../modules/alerting"

  name_prefix          = local.name_prefix
  alert_email          = var.alert_email
  database_instance_id = module.database.instance_id
  alb_arn_suffix       = module.compute.alb_arn_suffix
  ecs_cluster_name     = module.compute.cluster_name
  ecs_service_names    = keys(var.service_sizing)
  tags                 = local.tags
}

module "backups" {
  source = "../modules/backups"

  name_prefix           = local.name_prefix
  database_instance_arn = module.database.instance_arn
  retention_days        = var.backup_retention_days
  alert_topic_arn       = module.alerting.topic_arn
  tags                  = local.tags
}

# The DNS record pointing the domain at the ALB lives here, not in `dns_tls` or `compute` — it
# needs outputs from both, and putting it in either module would make that module depend on the
# other, when neither otherwise needs to know the other exists.
resource "aws_route53_record" "app" {
  zone_id = module.dns_tls.zone_id
  name    = var.domain_name
  type    = "A"

  alias {
    name                   = module.compute.alb_dns_name
    zone_id                = module.compute.alb_zone_id
    evaluate_target_health = true
  }
}
