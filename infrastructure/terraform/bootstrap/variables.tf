variable "aws_region" {
  description = "AWS region the state bucket and lock table live in."
  type        = string
  default     = "us-east-1"
}

variable "state_bucket_name" {
  description = "Globally-unique S3 bucket name for every environment's Terraform state."
  type        = string
  default     = "colt-terraform-state"
}

variable "lock_table_name" {
  description = "DynamoDB table name for Terraform state locking."
  type        = string
  default     = "colt-terraform-locks"
}
