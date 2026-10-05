# ============================================================
# Módulo network — VCN, gateways, route tables, subnets, seclists
# Segue os requisitos de rede do OKE (control plane <-> workers).
# ============================================================

# ---- VCN ----
resource "oci_core_vcn" "this" {
  compartment_id = var.compartment_ocid
  cidr_blocks    = [var.vcn_cidr]
  display_name   = "${var.cluster_name}-vcn"
  dns_label      = "okevcn"
  freeform_tags  = var.freeform_tags
}

# ---- Internet Gateway (subnets públicas) ----
resource "oci_core_internet_gateway" "igw" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.this.id
  display_name   = "${var.cluster_name}-igw"
  enabled        = true
  freeform_tags  = var.freeform_tags
}

# ---- NAT Gateway (egresso dos nodes privados) ----
resource "oci_core_nat_gateway" "nat" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.this.id
  display_name   = "${var.cluster_name}-nat"
  freeform_tags  = var.freeform_tags
}

# ---- Service Gateway (APIs/OCIR da Oracle sem sair pra internet) ----
data "oci_core_services" "all" {
  filter {
    name   = "name"
    values = ["All .* Services In Oracle Services Network"]
    regex  = true
  }
}

resource "oci_core_service_gateway" "sgw" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.this.id
  display_name   = "${var.cluster_name}-sgw"
  services {
    service_id = data.oci_core_services.all.services[0]["id"]
  }
  freeform_tags = var.freeform_tags
}

# ---- Route Tables ----
resource "oci_core_route_table" "public" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.this.id
  display_name   = "${var.cluster_name}-rt-public"
  route_rules {
    destination       = "0.0.0.0/0"
    destination_type  = "CIDR_BLOCK"
    network_entity_id = oci_core_internet_gateway.igw.id
  }
  freeform_tags = var.freeform_tags
}

resource "oci_core_route_table" "private" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.this.id
  display_name   = "${var.cluster_name}-rt-private"

  route_rules {
    destination       = "0.0.0.0/0"
    destination_type  = "CIDR_BLOCK"
    network_entity_id = oci_core_nat_gateway.nat.id
  }
  route_rules {
    destination       = data.oci_core_services.all.services[0]["cidr_block"]
    destination_type  = "SERVICE_CIDR_BLOCK"
    network_entity_id = oci_core_service_gateway.sgw.id
  }
  freeform_tags = var.freeform_tags
}

# ============================================================
# Security Lists
# ============================================================

# ---- Control plane (API endpoint) ----
resource "oci_core_security_list" "api" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.this.id
  display_name   = "${var.cluster_name}-sl-api"
  freeform_tags  = var.freeform_tags

  egress_security_rules {
    description      = "Control plane para OCI services (OCIR, APIs)"
    destination      = data.oci_core_services.all.services[0]["cidr_block"]
    destination_type = "SERVICE_CIDR_BLOCK"
    protocol         = "6"
    tcp_options {
      min = 443
      max = 443
    }
  }
  egress_security_rules {
    description      = "Control plane para os worker nodes"
    destination      = var.nodes_subnet_cidr
    destination_type = "CIDR_BLOCK"
    protocol         = "6"
  }
  egress_security_rules {
    description      = "Path discovery (ICMP)"
    destination      = var.nodes_subnet_cidr
    destination_type = "CIDR_BLOCK"
    protocol         = "1"
    icmp_options {
      type = 3
      code = 4
    }
  }

  ingress_security_rules {
    description = "kubectl (acesso admin) na API do Kubernetes"
    source      = var.admin_cidr
    source_type = "CIDR_BLOCK"
    protocol    = "6"
    tcp_options {
      min = 6443
      max = 6443
    }
  }
  ingress_security_rules {
    description = "Workers -> API do Kubernetes (6443)"
    source      = var.nodes_subnet_cidr
    source_type = "CIDR_BLOCK"
    protocol    = "6"
    tcp_options {
      min = 6443
      max = 6443
    }
  }
  ingress_security_rules {
    description = "Workers -> control plane (12250)"
    source      = var.nodes_subnet_cidr
    source_type = "CIDR_BLOCK"
    protocol    = "6"
    tcp_options {
      min = 12250
      max = 12250
    }
  }
  ingress_security_rules {
    description = "Path discovery (ICMP)"
    source      = var.nodes_subnet_cidr
    source_type = "CIDR_BLOCK"
    protocol    = "1"
    icmp_options {
      type = 3
      code = 4
    }
  }
}

# ---- Worker nodes ----
resource "oci_core_security_list" "nodes" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.this.id
  display_name   = "${var.cluster_name}-sl-nodes"
  freeform_tags  = var.freeform_tags

  egress_security_rules {
    description      = "Egresso total dos workers"
    destination      = "0.0.0.0/0"
    destination_type = "CIDR_BLOCK"
    protocol         = "all"
  }

  ingress_security_rules {
    description = "Comunicação node-a-node (mesma subnet)"
    source      = var.nodes_subnet_cidr
    source_type = "CIDR_BLOCK"
    protocol    = "all"
  }
  ingress_security_rules {
    description = "Control plane -> workers (todos TCP)"
    source      = var.api_subnet_cidr
    source_type = "CIDR_BLOCK"
    protocol    = "6"
  }
  ingress_security_rules {
    description = "Load Balancer -> NodePorts"
    source      = var.lb_subnet_cidr
    source_type = "CIDR_BLOCK"
    protocol    = "6"
    tcp_options {
      min = 30000
      max = 32767
    }
  }
  ingress_security_rules {
    description = "Load Balancer -> health check (10256)"
    source      = var.lb_subnet_cidr
    source_type = "CIDR_BLOCK"
    protocol    = "6"
    tcp_options {
      min = 10256
      max = 10256
    }
  }
  ingress_security_rules {
    description = "Path discovery (ICMP)"
    source      = "0.0.0.0/0"
    source_type = "CIDR_BLOCK"
    protocol    = "1"
    icmp_options {
      type = 3
      code = 4
    }
  }
}

# ---- API Gateway ----
resource "oci_core_security_list" "apigw" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.this.id
  display_name   = "${var.cluster_name}-sl-apigw"
  freeform_tags  = var.freeform_tags

  # Egresso total: o gateway precisa alcançar a URL pública do bucket.
  egress_security_rules {
    description      = "Egresso do API Gateway (alcançar o Object Storage)"
    destination      = "0.0.0.0/0"
    destination_type = "CIDR_BLOCK"
    protocol         = "all"
  }

  ingress_security_rules {
    description = "HTTP público"
    source      = "0.0.0.0/0"
    source_type = "CIDR_BLOCK"
    protocol    = "6"
    tcp_options {
      min = 80
      max = 80
    }
  }
  ingress_security_rules {
    description = "HTTPS público"
    source      = "0.0.0.0/0"
    source_type = "CIDR_BLOCK"
    protocol    = "6"
    tcp_options {
      min = 443
      max = 443
    }
  }
}

# ---- Load Balancers ----
resource "oci_core_security_list" "lb" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.this.id
  display_name   = "${var.cluster_name}-sl-lb"
  freeform_tags  = var.freeform_tags

  egress_security_rules {
    description      = "LB -> NodePorts dos workers"
    destination      = var.nodes_subnet_cidr
    destination_type = "CIDR_BLOCK"
    protocol         = "6"
    tcp_options {
      min = 30000
      max = 32767
    }
  }

  ingress_security_rules {
    description = "HTTP público"
    source      = "0.0.0.0/0"
    source_type = "CIDR_BLOCK"
    protocol    = "6"
    tcp_options {
      min = 80
      max = 80
    }
  }
  ingress_security_rules {
    description = "HTTPS público"
    source      = "0.0.0.0/0"
    source_type = "CIDR_BLOCK"
    protocol    = "6"
    tcp_options {
      min = 443
      max = 443
    }
  }
}

# ============================================================
# Subnets
# ============================================================
resource "oci_core_subnet" "api" {
  compartment_id             = var.compartment_ocid
  vcn_id                     = oci_core_vcn.this.id
  cidr_block                 = var.api_subnet_cidr
  display_name               = "${var.cluster_name}-subnet-api"
  dns_label                  = "api"
  route_table_id             = oci_core_route_table.public.id
  security_list_ids          = [oci_core_security_list.api.id]
  prohibit_public_ip_on_vnic = false
  freeform_tags              = var.freeform_tags
}

resource "oci_core_subnet" "lb" {
  compartment_id             = var.compartment_ocid
  vcn_id                     = oci_core_vcn.this.id
  cidr_block                 = var.lb_subnet_cidr
  display_name               = "${var.cluster_name}-subnet-lb"
  dns_label                  = "lb"
  route_table_id             = oci_core_route_table.public.id
  security_list_ids          = [oci_core_security_list.lb.id]
  prohibit_public_ip_on_vnic = false
  freeform_tags              = var.freeform_tags
}

resource "oci_core_subnet" "nodes" {
  compartment_id             = var.compartment_ocid
  vcn_id                     = oci_core_vcn.this.id
  cidr_block                 = var.nodes_subnet_cidr
  display_name               = "${var.cluster_name}-subnet-nodes"
  dns_label                  = "nodes"
  route_table_id             = oci_core_route_table.private.id
  security_list_ids          = [oci_core_security_list.nodes.id]
  prohibit_public_ip_on_vnic = true
  freeform_tags              = var.freeform_tags
}

# API Gateway (pública, regional)
resource "oci_core_subnet" "apigw" {
  compartment_id             = var.compartment_ocid
  vcn_id                     = oci_core_vcn.this.id
  cidr_block                 = var.apigw_subnet_cidr
  display_name               = "${var.cluster_name}-subnet-apigw"
  dns_label                  = "apigw"
  route_table_id             = oci_core_route_table.public.id
  security_list_ids          = [oci_core_security_list.apigw.id]
  prohibit_public_ip_on_vnic = false
  freeform_tags              = var.freeform_tags
}
