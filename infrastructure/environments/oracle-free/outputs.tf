output "public_ip" {
  description = "Point DNS (an A record for var.domain_name) at this, or just browse to it directly over HTTP if domain_name is empty."
  value       = module.compute.public_ip
}

output "ssh_command" {
  value = "ssh ubuntu@${module.compute.public_ip}"
}
