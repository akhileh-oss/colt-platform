variable "name_prefix" {
  type = string
}

variable "database_instance_arn" {
  type = string
}

variable "retention_days" {
  description = "CLAUDE.md §54's \"documented retention\": how long an AWS Backup-managed RDS snapshot is kept, independent of the RDS instance's own automated-backup window."
  type        = number
  default     = 35
}

variable "alert_topic_arn" {
  description = "Reused from the `alerting` module — one SNS topic, one subscribed inbox, for every alarm this environment raises."
  type        = string
}

variable "tags" {
  type    = map(string)
  default = {}
}
