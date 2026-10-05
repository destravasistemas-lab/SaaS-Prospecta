# ============================================================
# Variáveis de entrada
# ============================================================

# ---- Autenticação OCI ----
variable "tenancy_ocid" {
  type        = string
  description = "OCID da tenancy."
}

variable "user_ocid" {
  type        = string
  description = "OCID do usuário que criou a API Key."
}

variable "fingerprint" {
  type        = string
  description = "Fingerprint da API Key."
}

variable "private_key_path" {
  type        = string
  description = "Caminho para o arquivo .pem da API Key privada."
}

variable "region" {
  type        = string
  description = "Região da OCI (ex: sa-saopaulo-1, sa-vinhedo-1)."
  default     = "sa-saopaulo-1"
}

variable "compartment_ocid" {
  type        = string
  description = "OCID do compartment onde os recursos serão criados."
}

# ---- Rede ----
variable "vcn_cidr" {
  type        = string
  description = "CIDR da VCN."
  default     = "10.0.0.0/16"
}

variable "api_subnet_cidr" {
  type        = string
  description = "CIDR da subnet do endpoint da API do Kubernetes (pública)."
  default     = "10.0.0.0/28"
}

variable "lb_subnet_cidr" {
  type        = string
  description = "CIDR da subnet dos Load Balancers (pública)."
  default     = "10.0.1.0/24"
}

variable "nodes_subnet_cidr" {
  type        = string
  description = "CIDR da subnet dos worker nodes (privada)."
  default     = "10.0.2.0/24"
}

variable "apigw_subnet_cidr" {
  type        = string
  description = "CIDR da subnet do API Gateway (pública)."
  default     = "10.0.3.0/24"
}

variable "admin_cidr" {
  type        = string
  description = "CIDR autorizado a acessar a API do Kubernetes (kubectl). RECOMENDADO: use o IP público da sua máquina em /32. Padrão liberado (INSEGURO para produção)."
  default     = "0.0.0.0/0"
}

# ---- Cluster OKE ----
variable "cluster_name" {
  type        = string
  description = "Nome do cluster OKE."
  default     = "adstudioai-oke"
}

variable "kubernetes_version" {
  type        = string
  description = "Versão do Kubernetes. Vazio = usa a mais recente disponível."
  default     = ""
}

variable "pods_cidr" {
  type        = string
  description = "CIDR interno dos pods (Flannel)."
  default     = "10.244.0.0/16"
}

variable "services_cidr" {
  type        = string
  description = "CIDR interno dos services do Kubernetes."
  default     = "10.96.0.0/16"
}

# ---- Node Pool (ARM Always Free) ----
variable "node_shape" {
  type        = string
  description = "Shape dos nodes. VM.Standard.A1.Flex é o ARM Always Free."
  default     = "VM.Standard.A1.Flex"
}

variable "node_count" {
  type        = number
  description = "Quantidade de worker nodes."
  default     = 2
}

variable "node_ocpus" {
  type        = number
  description = "OCPUs por node. Free tier: total de 4 OCPUs entre todos os nodes A1."
  default     = 2
}

variable "node_memory_gbs" {
  type        = number
  description = "Memória (GB) por node. Free tier: total de 24 GB entre todos os nodes A1."
  default     = 12
}

variable "node_boot_volume_gbs" {
  type        = number
  description = "Tamanho do boot volume por node (GB). Free tier: até 200 GB total de block storage."
  default     = 50
}

variable "ssh_public_key" {
  type        = string
  description = "Chave SSH pública para acesso aos nodes (conteúdo do .pub)."
}

# ---- Frontend (Object Storage) ----
variable "frontend_bucket_name" {
  type        = string
  description = "Nome do bucket do Object Storage para o frontend estático."
  default     = "adstudioai-frontend"
}

# ---- Tags ----
variable "freeform_tags" {
  type        = map(string)
  description = "Tags aplicadas aos recursos."
  default = {
    project   = "adstudioai"
    managedby = "terraform"
  }
}
