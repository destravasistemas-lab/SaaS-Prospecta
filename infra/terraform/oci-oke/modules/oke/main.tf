# ============================================================
# Módulo oke — cluster BASIC (control plane grátis) + node pool ARM
# ============================================================

# ---- Availability domains ----
data "oci_identity_availability_domains" "ads" {
  compartment_id = var.tenancy_ocid
}

# ---- Versões de Kubernetes disponíveis ----
data "oci_containerengine_cluster_option" "this" {
  cluster_option_id = "all"
}

locals {
  # Se kubernetes_version não for informada, pega a mais recente disponível.
  k8s_version = var.kubernetes_version != "" ? var.kubernetes_version : element(
    reverse(sort(data.oci_containerengine_cluster_option.this.kubernetes_versions)), 0
  )
}

# ---- Cluster ----
resource "oci_containerengine_cluster" "this" {
  compartment_id     = var.compartment_ocid
  kubernetes_version = local.k8s_version
  name               = var.cluster_name
  vcn_id             = var.vcn_id
  type               = "BASIC_CLUSTER" # control plane Always Free
  freeform_tags      = var.freeform_tags

  endpoint_config {
    is_public_ip_enabled = true
    subnet_id            = var.api_subnet_id
  }

  options {
    service_lb_subnet_ids = [var.lb_subnet_id]

    add_ons {
      is_kubernetes_dashboard_enabled = false
      is_tiller_enabled               = false
    }

    kubernetes_network_config {
      pods_cidr     = var.pods_cidr
      services_cidr = var.services_cidr
    }
  }

  cluster_pod_network_options {
    cni_type = "FLANNEL_OVERLAY"
  }
}

# ---- Imagens compatíveis para o node pool ----
data "oci_containerengine_node_pool_option" "this" {
  node_pool_option_id = "all"
  compartment_id      = var.compartment_ocid
}

locals {
  k8s_ver_num = replace(local.k8s_version, "v", "")

  # Filtra imagens ARM (aarch64) compatíveis com a versão do cluster.
  arm_sources = [
    for s in data.oci_containerengine_node_pool_option.this.sources :
    s if can(regex("aarch64", s.source_name)) && can(regex(local.k8s_ver_num, s.source_name))
  ]

  # Fallback: qualquer imagem aarch64 se o filtro por versão não achar.
  arm_sources_any = [
    for s in data.oci_containerengine_node_pool_option.this.sources :
    s if can(regex("aarch64", s.source_name))
  ]

  node_image_id = length(local.arm_sources) > 0 ? local.arm_sources[0].image_id : local.arm_sources_any[0].image_id
}

# ---- Node Pool (ARM A1 Flex) ----
resource "oci_containerengine_node_pool" "this" {
  cluster_id         = oci_containerengine_cluster.this.id
  compartment_id     = var.compartment_ocid
  kubernetes_version = local.k8s_version
  name               = "${var.cluster_name}-arm-pool"
  node_shape         = var.node_shape
  ssh_public_key     = var.ssh_public_key
  freeform_tags      = var.freeform_tags

  node_shape_config {
    ocpus         = var.node_ocpus
    memory_in_gbs = var.node_memory_gbs
  }

  node_config_details {
    size = var.node_count

    # Distribui os nodes por todos os ADs disponíveis (ajuda com
    # a disponibilidade de capacidade ARM, que costuma ser escassa).
    dynamic "placement_configs" {
      for_each = data.oci_identity_availability_domains.ads.availability_domains
      content {
        availability_domain = placement_configs.value.name
        subnet_id           = var.nodes_subnet_id
      }
    }

    node_pool_pod_network_option_details {
      cni_type = "FLANNEL_OVERLAY"
    }
  }

  node_source_details {
    source_type             = "IMAGE"
    image_id                = local.node_image_id
    boot_volume_size_in_gbs = var.node_boot_volume_gbs
  }

  initial_node_labels {
    key   = "app"
    value = "adstudioai"
  }
}
