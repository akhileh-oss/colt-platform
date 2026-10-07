variable "name_prefix" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "public_subnet_ids" {
  type = list(string)
}

variable "private_subnet_ids" {
  type = list(string)
}

variable "alb_security_group_id" {
  type = string
}

variable "app_security_group_id" {
  type = string
}

variable "certificate_arn" {
  description = "ACM certificate ARN for the ALB's HTTPS listener (from the dns_tls module)."
  type        = string
}

variable "database_credentials_secret_arn" {
  type = string
}

variable "application_secret_arns" {
  description = "Map of logical secret name -> ARN (from the secrets module), granted to every task's execution role so it can inject them as container environment variables."
  type        = map(string)
}

variable "object_storage_bucket_arn" {
  type = string
}

variable "log_retention_days" {
  type    = number
  default = 30
}

#: One block per Fargate service this environment runs. `public` services (api, web) get an
#: ALB target group and listener rule on `path_pattern`; `public = false` (worker) does not.
variable "services" {
  description = <<-EOT
    Map of service name -> { image, cpu, memory, port, desired_count, public, path_pattern,
    health_check_path, environment (list of {name, value}) }. `image` is a full ECR URI with
    tag; this module does not build or push images (CLAUDE.md §26's CI/CD milestone owns that).
  EOT
  type = map(object({
    image             = string
    cpu               = number
    memory            = number
    port              = number
    desired_count     = number
    public            = bool
    path_pattern      = optional(string)
    health_check_path = optional(string, "/live")
    environment       = optional(list(object({ name = string, value = string })), [])
  }))
}

variable "tags" {
  type    = map(string)
  default = {}
}
