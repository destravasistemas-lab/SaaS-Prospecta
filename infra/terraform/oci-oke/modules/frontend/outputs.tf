# ============================================================
# Módulo frontend — outputs
# ============================================================
output "bucket_name" {
  description = "Nome do bucket."
  value       = oci_objectstorage_bucket.frontend.name
}

output "namespace" {
  description = "Namespace do Object Storage."
  value       = data.oci_objectstorage_namespace.ns.namespace
}

output "bucket_public_url_base" {
  description = "URL base pública dos objetos do bucket."
  value       = "https://objectstorage.${var.region}.oraclecloud.com/n/${data.oci_objectstorage_namespace.ns.namespace}/b/${oci_objectstorage_bucket.frontend.name}/o"
}

output "apigw_gateway_hostname" {
  description = "Hostname público do API Gateway."
  value       = oci_apigateway_gateway.this.hostname
}

output "frontend_url" {
  description = "URL final do frontend (via API Gateway com SPA routing)."
  value       = oci_apigateway_deployment.frontend.endpoint
}
