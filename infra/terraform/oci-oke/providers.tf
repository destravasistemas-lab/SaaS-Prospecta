# ============================================================
# Provider OCI — autenticação por API Key
# ============================================================
# Alternativa: rodar do OCI Cloud Shell (usa instance principal)
# ou apontar para o ~/.oci/config com `config_file_profile`.
# Aqui usamos as credenciais explícitas via variáveis.
# ============================================================
provider "oci" {
  tenancy_ocid     = var.tenancy_ocid
  user_ocid        = var.user_ocid
  fingerprint      = var.fingerprint
  private_key_path = var.private_key_path
  region           = var.region
}
