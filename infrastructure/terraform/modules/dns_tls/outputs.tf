output "zone_id" {
  value = local.zone_id
}

output "certificate_arn" {
  value = aws_acm_certificate_validation.this.certificate_arn
}

output "domain_name" {
  value = var.domain_name
}
