variable "name_prefix" {
  type = string
}

variable "private_subnet_ids" {
  type = list(string)
}

variable "security_group_id" {
  description = "The networking module's `cache_security_group_id`."
  type        = string
}

variable "node_type" {
  description = "Staging: cache.t4g.micro. Production: cache.r6g.large (CLAUDE.md §53.1's \"prefer managed Redis\")."
  type        = string
  default     = "cache.t4g.micro"
}

variable "multi_az" {
  description = "Automatic failover to a replica. False in staging, true in production."
  type        = bool
  default     = false
}

variable "tags" {
  type    = map(string)
  default = {}
}
