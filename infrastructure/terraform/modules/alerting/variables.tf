variable "name_prefix" {
  type = string
}

variable "alert_email" {
  description = "Email address subscribed to the alert topic. CLAUDE.md §70's incident-response runbooks assume a human is actually notified, not just that an alarm exists in a console nobody watches."
  type        = string
}

variable "database_instance_id" {
  type = string
}

variable "alb_arn_suffix" {
  type = string
}

variable "ecs_cluster_name" {
  type = string
}

variable "ecs_service_names" {
  type = list(string)
}

variable "tags" {
  type    = map(string)
  default = {}
}
