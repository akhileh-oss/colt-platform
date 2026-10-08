# No secret belongs in this file (CLAUDE.md §53) — every value here is already visible in a
# DNS record, a from:to email header, or a public ECR repository name. Replace the placeholders
# below with this deployment's real AWS account's values before the first `terraform apply`.

aws_region = "us-east-1"
azs        = ["us-east-1a", "us-east-1b"]

domain_name = "staging.colt.example.com"
alert_email = "platform-alerts@example.com"

# Must be globally unique across all of AWS.
object_storage_bucket_name = "colt-staging-objects-REPLACE_ME"

# Milestone 26 (CI/CD) is what actually builds and pushes these tags on every release; these
# are placeholders until that pipeline exists.
api_image    = "123456789012.dkr.ecr.us-east-1.amazonaws.com/colt-api:latest"
web_image    = "123456789012.dkr.ecr.us-east-1.amazonaws.com/colt-web:latest"
worker_image = "123456789012.dkr.ecr.us-east-1.amazonaws.com/colt-worker:latest"
