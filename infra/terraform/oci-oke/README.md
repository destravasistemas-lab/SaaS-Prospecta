# adStudioAI — Infra OCI (OKE + Object Storage)

Terraform **modularizado** para provisionar na Oracle Cloud (Always Free):

- **OKE** (Kubernetes gerenciado) — control plane grátis (`BASIC_CLUSTER`)
- **Node pool ARM** `VM.Standard.A1.Flex` — até 4 OCPUs / 24 GB grátis
- **Rede** completa (VCN, subnets, gateways, security lists)
- **Object Storage** — bucket para o frontend estático
- **API Gateway** — na frente do bucket: domínio único + SPA routing (deep-links → `index.html`)

O **banco** é externo gerenciado (Supabase/Neon/Render) — não é provisionado aqui, só referenciado via secret do Kubernetes.

## Estrutura

```
infra/
├── terraform/oci-oke/
│   ├── main.tf              # orquestra os módulos
│   ├── variables.tf · outputs.tf · providers.tf · versions.tf
│   ├── terraform.tfvars.example
│   └── modules/
│       ├── network/         # VCN, subnets, gateways, seclists
│       ├── oke/             # cluster + node pool ARM
│       └── frontend/        # bucket Object Storage + API Gateway (SPA)
└── k8s/                     # manifests do backend
    ├── namespace.yaml
    ├── backend-deployment.yaml
    ├── backend-service.yaml     # Service LoadBalancer (LB flex 10 Mbps)
    └── backend-secret.example.yaml
```

## Pré-requisitos

- [Terraform](https://developer.hashicorp.com/terraform/downloads) >= 1.5
- [OCI CLI](https://docs.oracle.com/en-us/iaas/Content/API/SDKDocs/cliinstall.htm) (para gerar o kubeconfig)
- [kubectl](https://kubernetes.io/docs/tasks/tools/)
- Uma conta OCI com **API Key** criada (Identity > Users > seu usuário > API Keys)

## 1. Provisionar a infraestrutura

```bash
cd infra/terraform/oci-oke

cp terraform.tfvars.example terraform.tfvars
# edite terraform.tfvars com seus OCIDs, região, chave SSH e admin_cidr

terraform init
terraform plan
terraform apply
```

> **Capacidade ARM:** o shape A1 (grátis) costuma ficar sem capacidade em
> alguns ADs. Se o `apply` falhar com *"Out of host capacity"*, tente outra
> região (ex: `sa-vinhedo-1`) ou reduza `node_count`/`node_ocpus` e reaplique.

## 2. Configurar o kubectl

O `terraform output` mostra o comando pronto:

```bash
terraform output -raw kubeconfig_command | bash
kubectl get nodes    # deve listar os nodes ARM em Ready
```

## 3. Publicar a imagem do backend no OCIR

```bash
# login no OCIR (region-key: gru=São Paulo, vcp=Vinhedo, etc.)
docker login <region-key>.ocir.io -u '<namespace>/<usuario>' -p '<auth-token>'

cd ../../../backend
docker build -t <region-key>.ocir.io/<namespace>/adstudioai-backend:latest .
docker push <region-key>.ocir.io/<namespace>/adstudioai-backend:latest
```

Crie o secret para o cluster puxar a imagem privada:

```bash
kubectl -n adstudioai create secret docker-registry ocir-secret \
  --docker-server=<region-key>.ocir.io \
  --docker-username='<namespace>/<usuario>' \
  --docker-password='<auth-token>' \
  --docker-email='seu@email.com'
```

## 4. Deploy do backend

```bash
cd ../infra/k8s

# 1) crie o secret com as variáveis de ambiente (ver backend-secret.example.yaml)
kubectl -n adstudioai create secret generic backend-env \
  --from-literal=DATABASE_URL='postgresql+asyncpg://user:pass@host:5432/db' \
  --from-literal=FERNET_KEY='...' \
  --from-literal=SECRET_KEY='...' \
  # ... demais chaves

# 2) ajuste a imagem em backend-deployment.yaml (REGION_KEY/NAMESPACE)

# 3) aplique os manifests
kubectl apply -f namespace.yaml
kubectl apply -f backend-deployment.yaml
kubectl apply -f backend-service.yaml

# pegue o IP público do Load Balancer
kubectl -n adstudioai get svc backend -w
```

## 5. Deploy do frontend (Object Storage)

```bash
cd ../../frontend
npm run build

NS=$(cd ../infra/terraform/oci-oke && terraform output -raw frontend_namespace)
BUCKET=$(cd ../infra/terraform/oci-oke && terraform output -raw frontend_bucket_name)

oci os object bulk-upload -ns "$NS" -bn "$BUCKET" \
  --src-dir dist --overwrite --content-type auto
```

Acesse o frontend pela URL do **API Gateway** (já com SPA routing):

```bash
terraform output -raw frontend_url
```

> **SPA routing resolvido pelo API Gateway:** o gateway roteia `/assets/*`
> para os objetos reais do bucket e **qualquer outra rota** (`/app/leads`,
> `/login`, etc.) para o `index.html` — deep-links funcionam. O build do Vite
> coloca os arquivos com hash sob `/assets/`, então o padrão encaixa direto.
>
> **CDN de verdade (edge cache global):** o API Gateway dá domínio único e
> roteamento, mas não é um CDN com cache de borda. Se precisar, coloque o
> **OCI CDN** (ou Cloudflare) na frente do gateway depois.

## Configuração cruzada (importante)

- O **frontend** precisa apontar para a URL pública do backend (IP/hostname do LB).
- O **backend** precisa liberar o domínio do frontend no `CORS_ORIGINS`.
- Frontend em HTTPS chamando backend em HTTP dá *mixed content* — coloque
  **TLS no backend** (cert-manager + ingress-nginx, ou cert no OCI LB).

## Estado remoto (opcional, recomendado para time)

Por padrão o state é **local**. Para compartilhar, use um bucket do Object
Storage como backend S3-compatível (crie um Customer Secret Key em Identity):

```hcl
# backend.tf
terraform {
  backend "s3" {
    bucket                      = "tf-state"
    key                         = "oci-oke/terraform.tfstate"
    region                      = "sa-saopaulo-1"
    endpoints                   = { s3 = "https://<namespace>.compat.objectstorage.sa-saopaulo-1.oraclecloud.com" }
    skip_region_validation      = true
    skip_credentials_validation = true
    skip_requesting_account_id  = true
    skip_s3_checksum            = true
    use_path_style              = true
  }
}
```

## Destruir tudo

```bash
terraform destroy
```
