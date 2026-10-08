variable "name_prefix" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "cluster_arn" {
  description = "The `compute` module's ECS cluster — Temporal runs alongside the application services rather than on a cluster of its own, one less cluster to operate."
  type        = string
}

variable "private_subnet_ids" {
  type = list(string)
}

variable "app_security_group_id" {
  description = "Temporal's frontend (7233) is reached by api/web/worker tasks in this same security group — already allowed by the networking module's `app_from_app` rule."
  type        = string
}

variable "execution_role_arn" {
  description = "Reused from the `compute` module: pulls the image, reads the database secret, writes logs."
  type        = string
}

variable "task_role_arn" {
  type = string
}

variable "database_host" {
  type = string
}

variable "database_port" {
  type = number
}

variable "database_credentials_secret_arn" {
  type = string
}

variable "image" {
  description = "Mirrors `docker-compose.yml`'s local `temporal` service's own pinned version."
  type        = string
  default     = "temporalio/auto-setup:1.29.3"
}

variable "cpu" {
  type    = number
  default = 1024
}

variable "memory" {
  type    = number
  default = 2048
}

variable "log_retention_days" {
  type    = number
  default = 30
}

variable "tags" {
  type    = map(string)
  default = {}
}
