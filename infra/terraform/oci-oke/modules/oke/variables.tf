# ============================================================
# Módulo oke — variáveis
# ============================================================
variable "compartment_ocid" {
  type        = string
  description = "OCID do compartment."
}

variable "tenancy_ocid" {
  type        = string
  description = "OCID da tenancy (para listar availability domains)."
}

variable "cluster_name" {
  type        = string
  description = "Nome do cluster OKE."
}

variable "kubernetes_version" {
  type        = string
  description = "Versão do Kubernetes. Vazio = usa a mais recente disponível."
  default     = ""
}

# ---- Rede (vinda do módulo network) ----
variable "vcn_id" {
  type        = string
  description = "OCID da VCN."
}

variable "api_subnet_id" {
  type        = string
  description = "OCID da subnet do endpoint da API."
}

variable "lb_subnet_id" {
  type        = string
  description = "OCID da subnet dos Load Balancers."
}

variable "nodes_subnet_id" {
  type        = string
  description = "OCID da subnet dos worker nodes."
}

variable "pods_cidr" {
  type        = string
  description = "CIDR interno dos pods (Flannel)."
}

variable "services_cidr" {
  type        = string
  description = "CIDR interno dos services."
}

# ---- Node pool ----
variable "node_shape" {
  type        = string
  description = "Shape dos nodes (VM.Standard.A1.Flex = ARM Always Free)."
}

variable "node_count" {
  type        = number
  description = "Quantidade de worker nodes."
}

variable "node_ocpus" {
  type        = number
  description = "OCPUs por node."
}

variable "node_memory_gbs" {
  type        = number
  description = "Memória (GB) por node."
}

variable "node_boot_volume_gbs" {
  type        = number
  description = "Boot volume por node (GB)."
}

variable "ssh_public_key" {
  type        = string
  description = "Chave SSH pública para os nodes."
}

variable "freeform_tags" {
  type        = map(string)
  description = "Tags aplicadas aos recursos."
  default     = {}
}
