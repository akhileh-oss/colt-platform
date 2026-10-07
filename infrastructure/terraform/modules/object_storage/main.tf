/*
 * S3 (CLAUDE.md §34, §53.1): the managed equivalent of the local `docker-compose.yml` `minio`
 * service. Versioned so an overwritten or deleted object is recoverable, encrypted at rest, and
 * never publicly reachable — every object this platform stores is tenant-owned data, served
 * back to a signed-in user through a presigned URL `colt_api` issues, never through a public
 * bucket URL.
 */

resource "aws_kms_key" "this" {
  description         = "${var.name_prefix} object storage encryption"
  enable_key_rotation = true
  tags                = var.tags
}

resource "aws_s3_bucket" "this" {
  bucket = var.bucket_name
  tags   = var.tags
}

resource "aws_s3_bucket_versioning" "this" {
  bucket = aws_s3_bucket.this.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "this" {
  bucket = aws_s3_bucket.this.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.this.arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "this" {
  bucket                  = aws_s3_bucket.this.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "this" {
  bucket = aws_s3_bucket.this.id

  rule {
    id     = "expire-noncurrent-versions"
    status = "Enabled"

    filter {} # applies to every object in the bucket, not a prefix-scoped subset

    noncurrent_version_expiration {
      noncurrent_days = var.noncurrent_version_expiration_days
    }
  }
}
