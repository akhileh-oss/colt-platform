# No secret belongs in this file (CLAUDE.md §53). Replace the placeholders below with this
# deployment's real AWS account's values before the first `terraform apply`.

aws_region = "us-east-1"
azs        = ["us-east-1a", "us-east-1b"]

domain_name = "colt.example.com"
alert_email = "platform-alerts@example.com"

# Must be globally unique across all of AWS.
object_storage_bucket_name = "colt-production-objects-REPLACE_ME"

# Milestone 26 (CI/CD) builds and promotes a specific, already-staging-soaked tag to
# production on every release — never `:latest` here (CLAUDE.md §88).
api_image    = "123456789012.dkr.ecr.us-east-1.amazonaws.com/colt-api:REPLACE_ME"
web_image    = "123456789012.dkr.ecr.us-east-1.amazonaws.com/colt-web:REPLACE_ME"
worker_image = "123456789012.dkr.ecr.us-east-1.amazonaws.com/colt-worker:REPLACE_ME"
