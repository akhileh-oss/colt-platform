variable "environment" {
  description = "\"staging\" or \"production\" — used as the resource name prefix and in every tag."
  type        = string
  validation {
    condition     = contains(["staging", "production"], var.environment)
    error_message = "environment must be \"staging\" or \"production\"."
  }
}

variable "aws_region" {
  type = string
}

variable "azs" {
  description = "At least two availability zones."
  type        = list(string)
}

variable "vpc_cidr" {
  type    = string
  default = "10.0.0.0/16"
}

variable "single_nat_gateway" {
  type    = bool
  default = true
}

variable "domain_name" {
  type = string
}

variable "create_dns_zone" {
  type    = bool
  default = true
}

variable "alert_email" {
  type = string
}

variable "database_instance_class" {
  type    = string
  default = "db.t4g.medium"
}

variable "database_allocated_storage_gb" {
  type    = number
  default = 50
}

variable "database_max_allocated_storage_gb" {
  type    = number
  default = 200
}

variable "database_multi_az" {
  type    = bool
  default = false
}

variable "database_backup_retention_days" {
  type    = number
  default = 7
}

variable "backup_retention_days" {
  description = "AWS Backup's own independent retention (`backups` module) — separate from `database_backup_retention_days`, which is RDS's own automated-backup window."
  type        = number
  default     = 35
}

variable "cache_node_type" {
  type    = string
  default = "cache.t4g.micro"
}

variable "cache_multi_az" {
  type    = bool
  default = false
}

variable "object_storage_bucket_name" {
  description = "Must be globally unique across all of AWS."
  type        = string
}

variable "application_secret_names" {
  type = list(string)
  default = [
    "anthropic-api-key",
    "apollo-api-key",
    "brave-api-key",
    "smtp-credentials",
    "keycloak-client-secret",
  ]
}

#: Image tags are supplied per environment (`terraform.tfvars`) rather than defaulted here —
#: CLAUDE.md §88's release-versioning requirement means a specific commit's image, never
#: `:latest`, is what any environment actually runs; Milestone 26 (CI/CD) is what pushes a new
#: tag and updates this value per release, this milestone only defines where it plugs in.
variable "api_image" {
  type = string
}

variable "web_image" {
  type = string
}

variable "worker_image" {
  type = string
}

variable "service_sizing" {
  description = "Per-service {cpu, memory, desired_count}. Production overrides these; staging runs the smallest Fargate shape that works."
  type = map(object({
    cpu           = number
    memory        = number
    desired_count = number
  }))
  default = {
    api    = { cpu = 512, memory = 1024, desired_count = 1 }
    web    = { cpu = 256, memory = 512, desired_count = 1 }
    worker = { cpu = 512, memory = 1024, desired_count = 1 }
  }
}

variable "tags" {
  type    = map(string)
  default = {}
}
