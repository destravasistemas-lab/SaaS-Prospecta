# ============================================================
# Root — outputs
# ============================================================
output "cluster_id" {
  description = "OCID do cluster OKE."
  value       = module.oke.cluster_id
}

output "cluster_name" {
  description = "Nome do cluster."
  value       = module.oke.cluster_name
}

output "kubernetes_version" {
  description = "Versão do Kubernetes provisionada."
  value       = module.oke.kubernetes_version
}

output "cluster_endpoint" {
  description = "Endpoint público da API do Kubernetes."
  value       = module.oke.cluster_endpoint
}

output "kubeconfig_command" {
  description = "Comando para gerar o kubeconfig local."
  value       = "oci ce cluster create-kubeconfig --cluster-id ${module.oke.cluster_id} --file $HOME/.kube/config --region ${var.region} --token-version 2.0.0 --kube-endpoint PUBLIC_ENDPOINT"
}

output "frontend_bucket_name" {
  description = "Nome do bucket do frontend."
  value       = module.frontend.bucket_name
}

output "frontend_namespace" {
  description = "Namespace do Object Storage."
  value       = module.frontend.namespace
}

output "frontend_public_url_base" {
  description = "URL base pública dos objetos do frontend (acesso direto ao bucket)."
  value       = module.frontend.bucket_public_url_base
}

output "frontend_url" {
  description = "URL final do frontend, servido pelo API Gateway (com SPA routing)."
  value       = module.frontend.frontend_url
}

output "apigw_gateway_hostname" {
  description = "Hostname público do API Gateway."
  value       = module.frontend.apigw_gateway_hostname
}
