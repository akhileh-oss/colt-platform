variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "azs" {
  type    = list(string)
  default = ["us-east-1a", "us-east-1b"]
}

variable "domain_name" {
  type = string
}

variable "alert_email" {
  type = string
}

variable "object_storage_bucket_name" {
  type = string
}

variable "api_image" {
  type = string
}

variable "web_image" {
  type = string
}

variable "worker_image" {
  type = string
}

variable "service_sizing" {
  description = "Production's own sizing — larger than the `environment` module's staging-shaped default, and at least 2 of each so a single task's loss during a deploy never drops a service to zero."
  type = map(object({
    cpu           = number
    memory        = number
    desired_count = number
  }))
  default = {
    api    = { cpu = 1024, memory = 2048, desired_count = 2 }
    web    = { cpu = 512, memory = 1024, desired_count = 2 }
    worker = { cpu = 1024, memory = 2048, desired_count = 2 }
  }
}
