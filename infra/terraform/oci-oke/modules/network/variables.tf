# ============================================================
# Módulo network — variáveis
# ============================================================
variable "compartment_ocid" {
  type        = string
  description = "OCID do compartment."
}

variable "cluster_name" {
  type        = string
  description = "Nome base usado no display_name dos recursos."
}

variable "vcn_cidr" {
  type        = string
  description = "CIDR da VCN."
}

variable "api_subnet_cidr" {
  type        = string
  description = "CIDR da subnet do endpoint da API do Kubernetes (pública)."
}

variable "lb_subnet_cidr" {
  type        = string
  description = "CIDR da subnet dos Load Balancers (pública)."
}

variable "nodes_subnet_cidr" {
  type        = string
  description = "CIDR da subnet dos worker nodes (privada)."
}

variable "apigw_subnet_cidr" {
  type        = string
  description = "CIDR da subnet do API Gateway (pública)."
}

variable "admin_cidr" {
  type        = string
  description = "CIDR autorizado a acessar a API do Kubernetes (kubectl)."
}

variable "freeform_tags" {
  type        = map(string)
  description = "Tags aplicadas aos recursos."
  default     = {}
}
