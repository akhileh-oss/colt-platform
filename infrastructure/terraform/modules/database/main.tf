/*
 * RDS for PostgreSQL (CLAUDE.md §53.1, §54): the managed equivalent of the local
 * `docker-compose.yml` `postgres` service, including the same `pgvector`/`pgcrypto` extensions
 * (`infrastructure/docker/postgres/init/01-extensions.sql` enables them locally; RDS Postgres
 * 15+ allow-lists both, so no parameter-group change is needed for either).
 *
 * The master password is generated here, never passed in as a variable — CLAUDE.md §53's "never
 * store production infrastructure secrets in Git" means no `.tfvars` file may ever hold it — and
 * stored only in Secrets Manager, read back by `colt_api`/`colt-workflows` worker tasks at
 * container start (`compute` module), never written to a Terraform output in plaintext.
 */

resource "random_password" "master" {
  length           = 32
  special          = true
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

resource "aws_db_subnet_group" "this" {
  name       = "${var.name_prefix}-db"
  subnet_ids = var.private_subnet_ids
  tags       = var.tags
}

resource "aws_kms_key" "database" {
  description         = "${var.name_prefix} RDS storage encryption"
  enable_key_rotation = true
  tags                = var.tags
}

resource "aws_db_instance" "this" {
  identifier     = "${var.name_prefix}-db"
  engine         = "postgres"
  engine_version = var.engine_version
  instance_class = var.instance_class

  allocated_storage     = var.allocated_storage_gb
  max_allocated_storage = var.max_allocated_storage_gb
  storage_type          = "gp3"
  storage_encrypted     = true
  kms_key_id            = aws_kms_key.database.arn

  db_name  = var.database_name
  username = var.master_username
  password = random_password.master.result
  port     = 5432

  db_subnet_group_name   = aws_db_subnet_group.this.name
  vpc_security_group_ids = [var.security_group_id]
  publicly_accessible    = false

  multi_az                = var.multi_az
  backup_retention_period = var.backup_retention_days
  backup_window           = "03:00-04:00"
  maintenance_window      = "mon:04:30-mon:05:30"

  deletion_protection       = true
  skip_final_snapshot       = false
  final_snapshot_identifier = "${var.name_prefix}-db-final"

  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]

  tags = var.tags
}

resource "aws_secretsmanager_secret" "master_credentials" {
  name                    = "${var.name_prefix}/database/master-credentials"
  recovery_window_in_days = 7
  tags                    = var.tags
}

resource "aws_secretsmanager_secret_version" "master_credentials" {
  secret_id = aws_secretsmanager_secret.master_credentials.id
  secret_string = jsonencode({
    username = var.master_username
    password = random_password.master.result
    host     = aws_db_instance.this.address
    port     = aws_db_instance.this.port
    dbname   = var.database_name
  })
}
