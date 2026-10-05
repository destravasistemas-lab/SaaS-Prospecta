# ============================================================
# Módulo network — outputs
# ============================================================
output "vcn_id" {
  description = "OCID da VCN."
  value       = oci_core_vcn.this.id
}

output "api_subnet_id" {
  description = "OCID da subnet do endpoint da API."
  value       = oci_core_subnet.api.id
}

output "lb_subnet_id" {
  description = "OCID da subnet dos Load Balancers."
  value       = oci_core_subnet.lb.id
}

output "nodes_subnet_id" {
  description = "OCID da subnet dos worker nodes."
  value       = oci_core_subnet.nodes.id
}

output "apigw_subnet_id" {
  description = "OCID da subnet do API Gateway."
  value       = oci_core_subnet.apigw.id
}
