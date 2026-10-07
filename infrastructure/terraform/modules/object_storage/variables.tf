variable "name_prefix" {
  type = string
}

variable "bucket_name" {
  description = "Globally-unique S3 bucket name. Must not collide across environments or accounts."
  type        = string
}

variable "noncurrent_version_expiration_days" {
  description = "How long a replaced/deleted object's prior version is kept before permanent deletion."
  type        = number
  default     = 90
}

variable "tags" {
  type    = map(string)
  default = {}
}
