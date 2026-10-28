output "instance_id" {
  value = oci_core_instance.this.id
}

output "public_ip" {
  value = oci_core_public_ip.reserved.ip_address
}

output "data_volume_id" {
  value = oci_core_volume.data.id
}
