/*
 * AWS Backup (CLAUDE.md §54): an independent, documented-retention snapshot policy for RDS, on
 * top of (not instead of) the RDS instance's own automated backups and point-in-time recovery
 * (`backup_retention_days` on the `database` module already enables both). Alerts fire on a
 * failed backup job — never only on a failed restore, since §54's "a backup that has never been
 * restored/tested is not considered proven" is this milestone's own honest admission that
 * restore testing is Milestone 28's job (the "Backup + Restore Drill" milestone), not this
 * one's — this module only proves backups are *taken* and *alerted on*, not yet *restorable*.
 */

resource "aws_backup_vault" "this" {
  name = "${var.name_prefix}-backup-vault"
  tags = var.tags
}

resource "aws_backup_plan" "this" {
  name = "${var.name_prefix}-backup-plan"

  rule {
    rule_name         = "daily"
    target_vault_name = aws_backup_vault.this.name
    schedule          = "cron(0 5 * * ? *)" # 05:00 UTC daily, outside the RDS maintenance window

    lifecycle {
      delete_after = var.retention_days
    }
  }

  tags = var.tags
}

resource "aws_backup_selection" "database" {
  name         = "${var.name_prefix}-database"
  plan_id      = aws_backup_plan.this.id
  iam_role_arn = aws_iam_role.backup.arn
  resources    = [var.database_instance_arn]
}

data "aws_iam_policy_document" "backup_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["backup.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "backup" {
  name               = "${var.name_prefix}-backup"
  assume_role_policy = data.aws_iam_policy_document.backup_assume_role.json
  tags               = var.tags
}

resource "aws_iam_role_policy_attachment" "backup" {
  role       = aws_iam_role.backup.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSBackupServiceRolePolicyForBackup"
}

resource "aws_backup_vault_notifications" "this" {
  backup_vault_name   = aws_backup_vault.this.name
  sns_topic_arn       = var.alert_topic_arn
  backup_vault_events = ["BACKUP_JOB_FAILED", "RESTORE_JOB_FAILED"]
}
