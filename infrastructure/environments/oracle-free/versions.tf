terraform {
  # OCI Cloud Shell (the easiest place to actually run this) ships Terraform 1.5.x — nothing in
  # this configuration needs anything newer, so the constraint matches what's really required
  # rather than copying the AWS environment's >= 1.9 out of habit.
  required_version = ">= 1.5"

  required_providers {
    oci = {
      source  = "oracle/oci"
      version = ">= 5.0, < 7.0" # verify against the current registry version before `apply`
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  # No remote backend: a remote backend on OCI's own free Object Storage (S3-compatible) is
  # possible but needs a bucket + customer secret key that must exist before this environment
  # does — its own bootstrapping problem, the same one `../../terraform/bootstrap` solves for
  # AWS. Deliberately out of scope for a single free environment one person runs; state is
  # local (`terraform.tfstate`, gitignored) here. Keep a copy of it somewhere durable — losing
  # it means Terraform no longer knows what it created, not that the running instance stops
  # working.
}

provider "oci" {
  region = var.region
  # Auth comes from ~/.oci/config (the OCI CLI's own config file) or the OCI_CLI_*/TF_VAR_*
  # environment variables documented in docs/operations/ORACLE_FREE_TIER_DEPLOYMENT.md — never
  # hard-coded here.
}
