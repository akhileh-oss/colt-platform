variable "compartment_id" {
  type = string
}

variable "name_prefix" {
  type = string
}

variable "subnet_id" {
  type = string
}

variable "nsg_id" {
  type = string
}

variable "ssh_public_key" {
  description = "Public half of the SSH keypair that can reach this instance. Generate with `ssh-keygen -t ed25519`; never commit the private half."
  type        = string
}

variable "image_id" {
  description = "OCID of a specific image to use instead of looking up the latest Canonical Ubuntu 22.04 for VM.Standard.A1.Flex."
  type        = string
  default     = null
}

# 4 OCPU / 24 GB is the entire Always Free Ampere A1 allowance for one tenancy. One instance at
# the full allowance, rather than splitting across several smaller ones, keeps this a single
# `docker compose` stack instead of a distributed system with no managed orchestration to run
# it on for free.
variable "ocpus" {
  type    = number
  default = 4
}

variable "memory_in_gbs" {
  type    = number
  default = 24
}

variable "boot_volume_size_in_gbs" {
  type    = number
  default = 50
}

variable "data_volume_size_in_gbs" {
  description = "Size of the dedicated data volume holding every service's persistent state (Postgres, Redis, MinIO, Keycloak). Boot (50) + this must stay at or under the 200 GB Always Free block-storage total."
  type        = number
  default     = 100
}

variable "data_device_path" {
  type    = string
  default = "/dev/oracleoci/oraclevdb"
}

variable "swap_size_mb" {
  type    = number
  default = 4096
}

variable "backup_retention_days" {
  type    = number
  default = 7
}

variable "domain_name" {
  description = "Domain pointed at this instance's reserved public IP. Empty string means Caddy serves plain HTTP with no TLS — see docs/operations/ORACLE_FREE_TIER_DEPLOYMENT.md."
  type        = string
  default     = ""
}

variable "api_image" {
  type = string
}

variable "web_image" {
  type = string
}

variable "worker_image" {
  type = string
}

variable "postgres_password" {
  type      = string
  sensitive = true
}

variable "redis_password" {
  type      = string
  sensitive = true
}

variable "minio_root_user" {
  type      = string
  sensitive = true
}

variable "minio_root_password" {
  type      = string
  sensitive = true
}

variable "keycloak_admin_password" {
  type      = string
  sensitive = true
}

variable "extra_env" {
  description = "Additional KEY=VALUE application config/secrets (ANTHROPIC_API_KEY, APP_SECRET_KEY, AUTH_CLIENT_SECRET, EMAIL_FROM_ADDRESS, ...) written verbatim into the instance's .env file."
  type        = map(string)
  default     = {}
  sensitive   = true
}

variable "tags" {
  type    = map(string)
  default = {}
}
