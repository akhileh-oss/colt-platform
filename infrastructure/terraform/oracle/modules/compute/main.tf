/*
 * One Always Free Ampere A1 instance running the entire Colt production stack as
 * `docker compose` — the free-tier alternative to AWS's ECS Fargate + ALB (CLAUDE.md §52/§53,
 * Milestone 25's `modules/compute`), which has no free tier at any usage level. See this
 * repository's `docs/operations/ORACLE_FREE_TIER_DEPLOYMENT.md` for why this trade (one box,
 * no managed HA, genuinely $0) was made and what it costs in resilience.
 */

data "oci_identity_availability_domains" "ads" {
  compartment_id = var.compartment_id
}

locals {
  availability_domain = data.oci_identity_availability_domains.ads.availability_domains[0].name
}

# Ubuntu's image OCID differs per region and changes over time; look it up rather than
# hard-coding one that would silently go stale or simply not exist in another region.
data "oci_core_images" "ubuntu" {
  compartment_id           = var.compartment_id
  operating_system         = "Canonical Ubuntu"
  operating_system_version = "22.04"
  shape                    = "VM.Standard.A1.Flex"
  sort_by                  = "TIMECREATED"
  sort_order               = "DESC"
}

locals {
  image_id = coalesce(var.image_id, data.oci_core_images.ubuntu.images[0].id)

  # Extra application secrets/config this module doesn't need to know the names of in advance
  # (ANTHROPIC_API_KEY, APP_SECRET_KEY, AUTH_CLIENT_SECRET, ...) — the caller supplies them as a
  # map; this just lowers them into .env lines, the same shape `docker compose --env-file`
  # expects.
  env_file_extra = join("\n", [for key, value in var.extra_env : "${key}=${value}"])
}

resource "oci_core_volume" "data" {
  compartment_id      = var.compartment_id
  availability_domain = local.availability_domain
  display_name        = "${var.name_prefix}-data"
  size_in_gbs         = var.data_volume_size_in_gbs
}

resource "oci_core_volume_backup_policy" "daily" {
  compartment_id = var.compartment_id
  display_name   = "${var.name_prefix}-daily-backup-policy"

  schedules {
    backup_type       = "INCREMENTAL"
    period            = "ONE_DAY"
    retention_seconds = var.backup_retention_days * 86400
    hour_of_day       = 5
    time_zone         = "UTC"
  }
}

# This proves backups are TAKEN, exactly like `modules/backups`'s own AWS Backup plan does for
# RDS — restoring one and verifying it is a drill (Milestone 28's job), not this resource's;
# §54's "a backup that has never been restored/tested is not considered proven" applies here
# precisely as it does there.
resource "oci_core_volume_backup_policy_assignment" "data" {
  asset_id  = oci_core_volume.data.id
  policy_id = oci_core_volume_backup_policy.daily.id
}

resource "oci_core_instance" "this" {
  compartment_id      = var.compartment_id
  availability_domain = local.availability_domain
  display_name        = "${var.name_prefix}-instance"
  shape               = "VM.Standard.A1.Flex"

  shape_config {
    ocpus         = var.ocpus
    memory_in_gbs = var.memory_in_gbs
  }

  source_details {
    source_type             = "image"
    source_id               = local.image_id
    boot_volume_size_in_gbs = var.boot_volume_size_in_gbs
  }

  create_vnic_details {
    subnet_id        = var.subnet_id
    nsg_ids          = [var.nsg_id]
    assign_public_ip = false # a RESERVED public IP is attached below instead
  }

  metadata = {
    ssh_authorized_keys = var.ssh_public_key
    user_data = base64encode(templatefile("${path.module}/cloud-init.sh.tftpl", {
      data_device    = var.data_device_path
      swap_size_mb   = var.swap_size_mb
      compose_file   = file("${path.module}/../../../../docker/oracle/docker-compose.prod.yml")
      otel_config    = file("${path.module}/../../../../docker/otel/collector-config.yaml")
      keycloak_realm = file("${path.module}/../../../../docker/keycloak/colt-realm.json")
      caddyfile = templatefile("${path.module}/../../../../docker/oracle/Caddyfile.tftpl", {
        domain_name = var.domain_name
      })
      domain_name             = var.domain_name
      postgres_password       = var.postgres_password
      redis_password          = var.redis_password
      minio_root_user         = var.minio_root_user
      minio_root_password     = var.minio_root_password
      keycloak_admin_password = var.keycloak_admin_password
      api_image               = var.api_image
      web_image               = var.web_image
      worker_image            = var.worker_image
      env_file_extra          = local.env_file_extra
    }))
  }

  freeform_tags = var.tags
}

# A reserved (not ephemeral) public IP: it survives the instance being recreated, so replacing
# the instance (e.g. to resize it) doesn't also mean re-pointing DNS.
data "oci_core_vnic_attachments" "instance" {
  compartment_id = var.compartment_id
  instance_id    = oci_core_instance.this.id
}

data "oci_core_private_ips" "instance" {
  vnic_id = data.oci_core_vnic_attachments.instance.vnic_attachments[0].vnic_id
}

resource "oci_core_public_ip" "reserved" {
  compartment_id = var.compartment_id
  display_name   = "${var.name_prefix}-public-ip"
  lifetime       = "RESERVED"
  private_ip_id  = data.oci_core_private_ips.instance.private_ips[0].id
}

resource "oci_core_volume_attachment" "data" {
  attachment_type = "paravirtualized"
  instance_id     = oci_core_instance.this.id
  volume_id       = oci_core_volume.data.id
  display_name    = "${var.name_prefix}-data-attachment"
}
