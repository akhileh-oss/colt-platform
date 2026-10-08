variable "name_prefix" {
  description = "Prefix for every resource name in this module, e.g. \"colt-staging\"."
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC."
  type        = string
  default     = "10.0.0.0/16"
}

variable "azs" {
  description = "Availability zones to spread public/private subnets across."
  type        = list(string)
}

variable "single_nat_gateway" {
  description = "Use one NAT gateway for every private subnet (cheaper) instead of one per AZ (more resilient). Staging uses one; production uses one per AZ."
  type        = bool
  default     = true
}

variable "tags" {
  description = "Tags applied to every resource this module creates."
  type        = map(string)
  default     = {}
}
