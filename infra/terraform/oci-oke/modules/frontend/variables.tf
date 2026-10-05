# ============================================================
# Módulo frontend — variáveis
# ============================================================
variable "compartment_ocid" {
  type        = string
  description = "OCID do compartment."
}

variable "bucket_name" {
  type        = string
  description = "Nome do bucket para o frontend estático."
}

variable "region" {
  type        = string
  description = "Região da OCI (usada para montar a URL pública do bucket)."
}

variable "apigw_subnet_id" {
  type        = string
  description = "OCID da subnet pública onde o API Gateway será criado."
}

variable "freeform_tags" {
  type        = map(string)
  description = "Tags aplicadas ao bucket."
  default     = {}
}
