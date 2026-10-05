# ============================================================
# Módulo oke — outputs
# ============================================================
output "cluster_id" {
  description = "OCID do cluster OKE."
  value       = oci_containerengine_cluster.this.id
}

output "cluster_name" {
  description = "Nome do cluster."
  value       = oci_containerengine_cluster.this.name
}

output "kubernetes_version" {
  description = "Versão do Kubernetes provisionada."
  value       = local.k8s_version
}

output "node_pool_id" {
  description = "OCID do node pool."
  value       = oci_containerengine_node_pool.this.id
}

output "cluster_endpoint" {
  description = "Endpoint público da API do Kubernetes."
  value       = oci_containerengine_cluster.this.endpoints[0].public_endpoint
}
