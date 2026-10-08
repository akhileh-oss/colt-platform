output "vcn_id" {
  value = oci_core_vcn.this.id
}

output "public_subnet_id" {
  value = oci_core_subnet.public.id
}

output "instance_nsg_id" {
  value = oci_core_network_security_group.instance.id
}
