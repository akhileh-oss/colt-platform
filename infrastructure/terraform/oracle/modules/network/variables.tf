variable "compartment_id" {
  description = "OCID of the compartment to create networking resources in."
  type        = string
}

variable "name_prefix" {
  description = "Prefix for every resource name in this module, e.g. \"colt-oracle-free\"."
  type        = string
}

variable "vcn_cidr" {
  type    = string
  default = "10.1.0.0/16"
}

variable "public_subnet_cidr" {
  type    = string
  default = "10.1.0.0/24"
}

variable "ssh_allowed_cidr" {
  description = "CIDR allowed to reach port 22. Default allows anywhere — set this to your own IP/32 once you know it; OCI free tier gives no bastion/VPN to narrow it further for you."
  type        = string
  default     = "0.0.0.0/0"
}
