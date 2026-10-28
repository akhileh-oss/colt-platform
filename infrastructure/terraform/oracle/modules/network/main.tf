/*
 * Oracle Cloud Infrastructure (OCI) networking for the free-tier deployment.
 *
 * Not a CLAUDE.md milestone — CLAUDE.md §53 specifies AWS (`../../modules/networking` and
 * friends, Milestone 25). This is a separate, user-requested alternative for anyone who cannot
 * carry AWS's recurring NAT Gateway / ALB / Fargate costs (none of those three has a free tier
 * at any usage level) and instead wants a single Always Free Ampere A1 instance running the
 * same `docker compose` stack Milestone 00's local dev environment already proves works.
 *
 * One public subnet, no NAT Gateway, no private subnet: a single instance has nothing behind
 * it that needs egress-only routing, so the AWS topology's private/public split doesn't apply
 * here. This is the actual cost saving, not just a cheaper version of the same shape.
 */

resource "oci_core_vcn" "this" {
  compartment_id = var.compartment_id
  display_name   = "${var.name_prefix}-vcn"
  cidr_blocks    = [var.vcn_cidr]
  dns_label      = replace(var.name_prefix, "-", "")
}

resource "oci_core_internet_gateway" "this" {
  compartment_id = var.compartment_id
  vcn_id         = oci_core_vcn.this.id
  display_name   = "${var.name_prefix}-igw"
  enabled        = true
}

resource "oci_core_route_table" "public" {
  compartment_id = var.compartment_id
  vcn_id         = oci_core_vcn.this.id
  display_name   = "${var.name_prefix}-public-rt"

  route_rules {
    destination       = "0.0.0.0/0"
    destination_type  = "CIDR_BLOCK"
    network_entity_id = oci_core_internet_gateway.this.id
  }
}

resource "oci_core_subnet" "public" {
  compartment_id             = var.compartment_id
  vcn_id                     = oci_core_vcn.this.id
  display_name               = "${var.name_prefix}-public-subnet"
  cidr_block                 = var.public_subnet_cidr
  route_table_id             = oci_core_route_table.public.id
  prohibit_public_ip_on_vnic = false
  dns_label                  = "public"
}

# --- Network Security Group: everything this one instance needs to expose, nothing more ------

resource "oci_core_network_security_group" "instance" {
  compartment_id = var.compartment_id
  vcn_id         = oci_core_vcn.this.id
  display_name   = "${var.name_prefix}-instance-nsg"
}

resource "oci_core_network_security_group_security_rule" "ssh_ingress" {
  network_security_group_id = oci_core_network_security_group.instance.id
  direction                 = "INGRESS"
  protocol                  = "6" # TCP
  source                    = var.ssh_allowed_cidr
  source_type               = "CIDR_BLOCK"

  tcp_options {
    destination_port_range {
      min = 22
      max = 22
    }
  }
}

resource "oci_core_network_security_group_security_rule" "http_ingress" {
  network_security_group_id = oci_core_network_security_group.instance.id
  direction                 = "INGRESS"
  protocol                  = "6"
  source                    = "0.0.0.0/0"
  source_type               = "CIDR_BLOCK"

  tcp_options {
    destination_port_range {
      min = 80
      max = 80
    }
  }
}

resource "oci_core_network_security_group_security_rule" "https_ingress" {
  network_security_group_id = oci_core_network_security_group.instance.id
  direction                 = "INGRESS"
  protocol                  = "6"
  source                    = "0.0.0.0/0"
  source_type               = "CIDR_BLOCK"

  tcp_options {
    destination_port_range {
      min = 443
      max = 443
    }
  }
}

# ICMP (type 3 code 4 — fragmentation needed) must be allowed inbound or path-MTU discovery
# breaks for clients behind a smaller-MTU link; OCI's own docs call this out explicitly.
resource "oci_core_network_security_group_security_rule" "icmp_path_mtu" {
  network_security_group_id = oci_core_network_security_group.instance.id
  direction                 = "INGRESS"
  protocol                  = "1" # ICMP
  source                    = "0.0.0.0/0"
  source_type               = "CIDR_BLOCK"

  icmp_options {
    type = 3
    code = 4
  }
}

resource "oci_core_network_security_group_security_rule" "all_egress" {
  network_security_group_id = oci_core_network_security_group.instance.id
  direction                 = "EGRESS"
  protocol                  = "all"
  destination               = "0.0.0.0/0"
  destination_type          = "CIDR_BLOCK"
}
