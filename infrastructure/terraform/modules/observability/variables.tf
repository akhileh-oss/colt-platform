variable "name_prefix" {
  type = string
}

variable "database_instance_id" {
  type = string
}

variable "alb_arn_suffix" {
  description = "The `aws_lb.this.arn_suffix` the ALB's own CloudWatch metrics are published under."
  type        = string
}

variable "ecs_cluster_name" {
  type = string
}

variable "tags" {
  type    = map(string)
  default = {}
}
