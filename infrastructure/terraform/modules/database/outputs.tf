output "address" {
  value = aws_db_instance.this.address
}

output "instance_id" {
  description = "The RDS instance identifier (e.g. \"colt-staging-db\") — what CloudWatch's `DBInstanceIdentifier` dimension expects, not the DNS address."
  value       = aws_db_instance.this.id
}

output "port" {
  value = aws_db_instance.this.port
}

output "database_name" {
  value = aws_db_instance.this.db_name
}

output "credentials_secret_arn" {
  description = "Secrets Manager ARN holding the master username/password/host/port/dbname."
  value       = aws_secretsmanager_secret.master_credentials.arn
}

output "instance_arn" {
  value = aws_db_instance.this.arn
}

output "master_username" {
  value = var.master_username
}

output "master_password" {
  description = "Only consumed at apply time by the `temporal` module's `postgresql` provider, to create Temporal's own databases on this instance — never written to a container's environment, which reads the same value back from `credentials_secret_arn` instead."
  value       = random_password.master.result
  sensitive   = true
}
