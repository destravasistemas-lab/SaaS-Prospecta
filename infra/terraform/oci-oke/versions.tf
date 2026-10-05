# ============================================================
# Versões do Terraform e providers
# ============================================================
terraform {
  required_version = ">= 1.5.0"

  required_providers {
    oci = {
      source  = "oracle/oci"
      version = ">= 5.30.0"
    }
  }

  # Estado local por padrão. Para produção, migre para um bucket
  # do Object Storage da OCI (backend "http"/"s3-compatible") ou
  # OCI Object Storage nativo. Exemplo comentado no README.
}
