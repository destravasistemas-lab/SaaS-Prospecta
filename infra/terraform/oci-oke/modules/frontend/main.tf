# ============================================================
# Módulo frontend — bucket do Object Storage (site estático)
# ============================================================
# O Object Storage da OCI serve objetos públicos via URL, mas NÃO faz
# reescrita de rota (404 -> index.html) como o S3 website. Para uma SPA
# com deep-links, coloque um OCI API Gateway ou CDN na frente (ver README).
# ============================================================

data "oci_objectstorage_namespace" "ns" {
  compartment_id = var.compartment_ocid
}

resource "oci_objectstorage_bucket" "frontend" {
  compartment_id = var.compartment_ocid
  namespace      = data.oci_objectstorage_namespace.ns.namespace
  name           = var.bucket_name
  access_type    = "ObjectRead" # leitura pública dos objetos
  freeform_tags  = var.freeform_tags
}

# ============================================================
# API Gateway na frente do bucket (domínio único + SPA routing)
# ============================================================
locals {
  # URL base dos objetos do bucket (endpoint público do Object Storage).
  bucket_o_url = "https://objectstorage.${var.region}.oraclecloud.com/n/${data.oci_objectstorage_namespace.ns.namespace}/b/${oci_objectstorage_bucket.frontend.name}/o"
}

resource "oci_apigateway_gateway" "this" {
  compartment_id = var.compartment_ocid
  endpoint_type  = "PUBLIC"
  subnet_id      = var.apigw_subnet_id
  display_name   = "${var.bucket_name}-apigw"
  freeform_tags  = var.freeform_tags
}

resource "oci_apigateway_deployment" "frontend" {
  compartment_id = var.compartment_ocid
  gateway_id     = oci_apigateway_gateway.this.id
  display_name   = "${var.bucket_name}-spa"
  path_prefix    = "/"
  freeform_tags  = var.freeform_tags

  specification {
    # ---- Assets estáticos (JS/CSS com hash) -> objetos reais ----
    # O Vite coloca tudo sob /assets/. Rota mais específica tem prioridade.
    routes {
      path    = "/assets/{pathName*}"
      methods = ["GET", "HEAD"]
      backend {
        type = "HTTP_BACKEND"
        # $${...} é literal para o API Gateway (Terraform não interpola).
        url = "${local.bucket_o_url}/assets/$${request.path[pathName]}"
      }
    }

    # ---- Arquivos soltos na raiz (favicon, robots, etc.) ----
    routes {
      path    = "/favicon.ico"
      methods = ["GET", "HEAD"]
      backend {
        type = "HTTP_BACKEND"
        url  = "${local.bucket_o_url}/favicon.ico"
      }
    }

    # ---- Fallback do SPA: qualquer outra rota serve o index.html ----
    routes {
      path    = "/{pathName*}"
      methods = ["GET", "HEAD"]
      backend {
        type = "HTTP_BACKEND"
        url  = "${local.bucket_o_url}/index.html"
      }
    }
  }
}
