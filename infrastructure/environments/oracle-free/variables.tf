variable "region" {
  description = "OCI region, e.g. \"us-ashburn-1\". Always Free Ampere A1 capacity is region-specific and sometimes unavailable — see docs/operations/ORACLE_FREE_TIER_DEPLOYMENT.md."
  type        = string
}

variable "compartment_id" {
  description = "OCID of the compartment to create everything in. Using the tenancy's root compartment is fine for a single free deployment."
  type        = string
}

variable "name_prefix" {
  type    = string
  default = "colt-oracle-free"
}

variable "ssh_public_key" {
  type = string
}

variable "ssh_allowed_cidr" {
  description = "CIDR allowed to SSH to the instance. Default is open; narrow this to your own IP once you know it."
  type        = string
  default     = "0.0.0.0/0"
}

variable "domain_name" {
  description = "Domain pointed at the instance's reserved public IP, for automatic HTTPS via Caddy. Empty string serves plain HTTP only."
  type        = string
  default     = ""
}

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
  type    = number
  default = 100
}

variable "backup_retention_days" {
  type    = number
  default = 7
}

variable "api_image" {
  description = "Full image reference, e.g. ghcr.io/akhileh-oss/colt-platform-api:latest — built and pushed by .github/workflows/build-images-ghcr.yml."
  type        = string
}

variable "web_image" {
  type = string
}

variable "worker_image" {
  type = string
}

variable "extra_env" {
  description = "Application secrets/config this Terraform doesn't model explicitly — at minimum ANTHROPIC_API_KEY and APP_SECRET_KEY. See terraform.tfvars.example."
  type        = map(string)
  sensitive   = true
  default     = {}
}

variable "tags" {
  type    = map(string)
  default = { Project = "colt", ManagedBy = "terraform", Environment = "oracle-free" }
}
