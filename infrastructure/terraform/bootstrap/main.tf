/*
 * One-time bootstrap: the S3 bucket and DynamoDB table every environment's own Terraform state
 * lives in (CLAUDE.md §53's "remote Terraform state with locking"). This cannot itself use that
 * backend — nothing exists yet for it to point at — so it is applied exactly once per AWS
 * account, by hand, before `infrastructure/environments/staging` or `production` is ever
 * initialized, and its own state is kept locally (or moved aside manually) rather than chasing
 * the same remote-state requirement it exists to satisfy for everything else.
 */

terraform {
  required_version = ">= 1.9"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

resource "aws_s3_bucket" "terraform_state" {
  bucket = var.state_bucket_name

  # Terraform state has no legitimate reason to ever be deleted out from under a running
  # environment; this is the one bucket in the whole stack that must survive `terraform destroy`
  # run against the wrong target by mistake.
  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_versioning" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "aws:kms"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "terraform_state" {
  bucket                  = aws_s3_bucket.terraform_state.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_dynamodb_table" "terraform_lock" {
  name         = var.lock_table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"

  attribute {
    name = "LockID"
    type = "S"
  }

  lifecycle {
    prevent_destroy = true
  }
}
