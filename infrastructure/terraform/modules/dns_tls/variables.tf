variable "domain_name" {
  description = "The apex domain this environment is served under, e.g. \"staging.colt.example.com\" or \"colt.example.com\"."
  type        = string
}

variable "create_zone" {
  description = "Create a new Route53 hosted zone for `domain_name`. False when it's a subdomain delegated from a zone this Terraform doesn't own."
  type        = bool
  default     = true
}

variable "tags" {
  type    = map(string)
  default = {}
}
