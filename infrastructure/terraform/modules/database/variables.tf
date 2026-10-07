variable "name_prefix" {
  type = string
}

variable "private_subnet_ids" {
  type = list(string)
}

variable "security_group_id" {
  description = "The networking module's `database_security_group_id` — only app tasks reach port 5432."
  type        = string
}

variable "instance_class" {
  description = "RDS instance class. Staging: db.t4g.medium. Production: db.r6g.large (CLAUDE.md §53.1's \"prefer managed Postgres\")."
  type        = string
  default     = "db.t4g.medium"
}

variable "allocated_storage_gb" {
  type    = number
  default = 50
}

variable "max_allocated_storage_gb" {
  description = "Storage autoscaling ceiling."
  type        = number
  default     = 200
}

variable "multi_az" {
  description = "Standby replica in a second AZ. False in staging, true in production."
  type        = bool
  default     = false
}

variable "backup_retention_days" {
  description = "CLAUDE.md §54 (Database backups). 7 in staging, 30 in production."
  type        = number
  default     = 7
}

variable "engine_version" {
  description = "PostgreSQL major.minor — must support the `pgvector`/`pgcrypto` extensions `infrastructure/docker/postgres/init/01-extensions.sql` enables locally."
  type        = string
  default     = "16.4"
}

variable "database_name" {
  type    = string
  default = "colt"
}

variable "master_username" {
  description = "The migration-privileged role (`colt` locally, ADR-0005) — distinct from the restricted `colt_app` runtime role the application actually connects as."
  type        = string
  default     = "colt"
}

variable "tags" {
  type    = map(string)
  default = {}
}
