# ============================================================
# Root — orquestra os módulos: network -> oke, e frontend
# ============================================================

module "network" {
  source = "./modules/network"

  compartment_ocid  = var.compartment_ocid
  cluster_name      = var.cluster_name
  vcn_cidr          = var.vcn_cidr
  api_subnet_cidr   = var.api_subnet_cidr
  lb_subnet_cidr    = var.lb_subnet_cidr
  nodes_subnet_cidr = var.nodes_subnet_cidr
  apigw_subnet_cidr = var.apigw_subnet_cidr
  admin_cidr        = var.admin_cidr
  freeform_tags     = var.freeform_tags
}

module "oke" {
  source = "./modules/oke"

  compartment_ocid   = var.compartment_ocid
  tenancy_ocid       = var.tenancy_ocid
  cluster_name       = var.cluster_name
  kubernetes_version = var.kubernetes_version

  vcn_id          = module.network.vcn_id
  api_subnet_id   = module.network.api_subnet_id
  lb_subnet_id    = module.network.lb_subnet_id
  nodes_subnet_id = module.network.nodes_subnet_id

  pods_cidr     = var.pods_cidr
  services_cidr = var.services_cidr

  node_shape           = var.node_shape
  node_count           = var.node_count
  node_ocpus           = var.node_ocpus
  node_memory_gbs      = var.node_memory_gbs
  node_boot_volume_gbs = var.node_boot_volume_gbs
  ssh_public_key       = var.ssh_public_key

  freeform_tags = var.freeform_tags
}

module "frontend" {
  source = "./modules/frontend"

  compartment_ocid = var.compartment_ocid
  bucket_name      = var.frontend_bucket_name
  region           = var.region
  apigw_subnet_id  = module.network.apigw_subnet_id
  freeform_tags    = var.freeform_tags
}
