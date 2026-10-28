# Oracle Cloud "Always Free" deployment

Not a `CLAUDE.md` milestone. `CLAUDE.md` §53 specifies AWS for production (Milestone 25,
`infrastructure/terraform/{modules,environment}` + `environments/{staging,production}`). This
is a separate, user-requested alternative for running the same application as a real, stable,
publicly reachable system with **no recurring bill** — AWS's ECS Fargate, Application Load
Balancer, and NAT Gateway have no free tier at any usage level, so no amount of AWS cost-cutting
gets that architecture to $0/month. This document covers the one that actually can.

## What this actually is

One Oracle Cloud Infrastructure (OCI) "Always Free" Ampere A1 compute instance — 4 OCPUs, 24 GB
RAM, the _entire_ Always Free Arm compute allowance for one tenancy — running the full stack
(Postgres, Redis, Temporal, MinIO, Keycloak, the OTel collector, and the `api`/`worker`/`web`
application containers) as one `docker compose` deployment, the same shape
`docker-compose.yml` already proves works in local development. Terraform:
`infrastructure/terraform/oracle/modules/{network,compute}` (leaf modules) and
`infrastructure/environments/oracle-free` (the root you actually run).

## What is and isn't genuinely free

| Resource                                  | OCI Always Free covers                                                                                                   | Notes                                                                                                                                                                                                                                                            |
| ----------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Compute (4 OCPU / 24 GB Ampere A1)        | Yes, forever — not a 12-month clock                                                                                      | Capacity is real but finite per region; a fresh signup sometimes hits "Out of host capacity" on A1 and has to retry a different region/time                                                                                                                      |
| Boot + block volumes (up to 200 GB total) | Yes                                                                                                                      | This config uses 50 GB boot + 100 GB data = 150 GB, leaving headroom                                                                                                                                                                                             |
| Volume backups                            | Yes, within a modest free count/retention — verify the current limit in the OCI console before relying on long retention | `backup_retention_days` defaults to 7                                                                                                                                                                                                                            |
| Outbound data transfer (10 TB/month)      | Yes                                                                                                                      | Far more than this deployment will use                                                                                                                                                                                                                           |
| Reserved public IP                        | Yes (1 per Always Free compute instance)                                                                                 | Used here so resizing the instance doesn't change DNS                                                                                                                                                                                                            |
| A domain name                             | **No**                                                                                                                   | Not an OCI resource; buy one anywhere, or run HTTP-only on the raw IP (`domain_name = ""`)                                                                                                                                                                       |
| A managed secrets service                 | **No**                                                                                                                   | OCI has no Always Free equivalent of AWS Secrets Manager — see "Secrets" below                                                                                                                                                                                   |
| A managed load balancer / managed TLS     | Not used here                                                                                                            | OCI does have a free Flexible Load Balancer (1 instance, 10 Mbps), but this deployment terminates TLS with Caddy directly on the instance instead, to avoid the LB's own TLS-certificate Terraform wiring — a reasonable free upgrade path later, not built here |

**The real trade for $0, stated plainly:** this is one computer. AWS's Fargate+ALB+Multi-AZ
RDS/Redis design (Milestone 25) survives losing an entire availability zone; this does not
survive losing this one instance. If OCI performs maintenance on it, or it crashes, the
application is down until it restarts (Docker's own `restart: unless-stopped` policy brings the
containers back automatically once the box is back; nothing fails over to another box, because
there isn't one). That is the actual cost of free — not a smaller version of AWS's resilience,
a different one.

## Secrets

With no free managed secrets service, every credential (database password, `ANTHROPIC_API_KEY`,
etc.) is generated or supplied by Terraform and written once, by cloud-init, into
`/data/colt/.env` on the instance itself (`chmod 600`, root-owned). Two consequences worth
knowing before you `apply`:

- **`terraform.tfstate` contains every secret in plaintext.** It is local to wherever you run
  `terraform apply` from (no remote backend is configured — see `versions.tf`'s own comment for
  why) and is gitignored. Keep it somewhere durable and access-controlled; losing it doesn't
  break the running instance, but it does mean Terraform forgets what it created.
- **Rotating a secret means a `terraform apply`,** which re-renders cloud-init — but cloud-init
  only runs once per instance, on first boot. Changing `extra_env`/the generated passwords and
  re-applying will **not** update the already-running instance's `.env` by itself. To actually
  rotate something: SSH in, edit `/data/colt/.env` by hand, then `cd /data/colt && docker
compose up -d` to apply it, or replace the instance (`terraform taint`/`apply`) to re-run
  cloud-init from scratch against the new value.

## One-time account setup (not automated by this Terraform)

1. Create an OCI account. Card verification is required even for Always Free; you are not
   charged unless you explicitly upgrade to a paid tier.
2. Create an API signing key for Terraform: OCI console → your profile → "API keys" → "Add API
   key", then put the resulting values into `~/.oci/config`:

   ```ini
   [DEFAULT]
   user=ocid1.user.oc1..xxxx
   fingerprint=xx:xx:...
   tenancy=ocid1.tenancy.oc1..xxxx
   region=us-ashburn-1
   key_file=~/.oci/oci_api_key.pem
   ```

   The `oci` Terraform provider reads this file automatically; nothing in this repository needs
   to know these values.

3. Generate an SSH keypair if you don't already have one: `ssh-keygen -t ed25519`.
4. Decide on a region. Always Free Ampere A1 capacity is genuinely finite and sometimes
   unavailable in busy regions/times — if `terraform apply` fails with "Out of host capacity",
   retry later or in a different region, rather than assuming the deployment is broken.
5. Optional: buy/own a domain and be ready to point an A record at the output `public_ip` once
   it exists.

## Building and deploying

```bash
# 1. Build images and push them to GHCR (free; avoids the Docker Hub rate-limiting this
#    sandbox hit in Milestone 26). Repository Actions tab → "Build images (GHCR)" → Run
#    workflow — or push a tag if you wire that trigger in yourself.

# 2. Configure this environment.
cd infrastructure/environments/oracle-free
cp terraform.tfvars.example terraform.tfvars
# edit terraform.tfvars: region, compartment_id, ssh_public_key, domain_name, extra_env

# 3. Apply.
terraform init
terraform plan   # review before creating real (if free) resources
terraform apply

# 4. Point DNS (if you set domain_name) at the `public_ip` output. Caddy requests a Let's
#    Encrypt certificate automatically on first request to that hostname — no further action.

# 5. Watch first-boot provisioning.
ssh ubuntu@$(terraform output -raw public_ip)
sudo tail -f /var/log/colt-cloud-init.log
```

## Operating it

```bash
ssh ubuntu@<public_ip>
cd /data/colt
sudo systemctl status colt         # the compose stack as a systemd unit
docker compose ps                  # per-container status
docker compose logs -f api         # any service's logs
```

## Backup + restore (the OCI analog of Milestone 28)

The data volume backup policy (`oci_core_volume_backup_policy` + `_assignment` in the `compute`
module) proves backups are **taken** — it does not prove they're restorable. CLAUDE.md §54's "a
backup that has never been restored/tested is not considered proven" applies here exactly as it
does to the AWS `modules/backups` — restoring one, for real, into a new volume and verifying its
contents is the actual drill:

1. OCI console (or `oci bv backup list`) → find the data volume's latest backup.
2. Create a new volume from that backup (`oci bv volume create --volume-backup-id ...`), in the
   same availability domain as a throwaway test instance.
3. Attach it to a temporary instance, mount it, and diff its `/data/colt/postgres` (or run
   `pg_dump`/row counts, same approach `scripts/backup_restore_drill.sh` uses for the AWS/local
   case) against the live instance's data.
4. Delete the temporary instance and volume afterward — they count against the same 200 GB
   Always Free block-storage pool as everything else.

This has **not** been run in this sandbox — no OCI account exists here to run it against
(matching Milestone 25/28's own "`NOT RUN`" precedent for anything that needs real infrastructure
this sandbox cannot provide).

## Tearing down

```bash
cd infrastructure/environments/oracle-free
terraform destroy
```

Nothing here costs money even left running indefinitely (within the Always Free limits above),
so there's no financial urgency to `destroy` — but regions do occasionally fail "Out of host
capacity" on _re_-creating an A1 instance, so don't destroy and recreate casually if the box is
otherwise healthy.
