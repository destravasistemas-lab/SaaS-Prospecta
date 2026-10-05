"""
GUIA DE SEGURANÇA MULTI-TENANT

Este guia descreve as práticas obrigatórias para garantir isolamento
de dados entre accounts (clientes) e evitar vazamento de dados.
"""

# ============================================================================
# 1. VALIDAÇÃO DE TENANT EM TODAS AS QUERIES
# ============================================================================

"""
✅ CORRETO - Com validação de tenant_id:

from app.core.tenant_security import require_tenant_owner

@router.get("/my-data")
async def get_data(
    db: AsyncSession = Depends(get_db),
    account: Account = Depends(require_tenant_owner),
):
    # SEMPRE filtrar por account_id
    stmt = select(MyModel).where(
        MyModel.account_id == account.id  # ✅ IMPORTANTE
    )
    result = await db.execute(stmt)
    data = result.scalars().all()
    return data


❌ ERRADO - Sem validação:

@router.get("/my-data")
async def get_data(db: AsyncSession = Depends(get_db)):
    # BUG: qualquer pessoa pode ver todos os dados
    stmt = select(MyModel)  # ❌ SEM FILTRO
    result = await db.execute(stmt)
    data = result.scalars().all()
    return data
"""

# ============================================================================
# 2. CHECKLIST PARA CRIAR NOVO ENDPOINT
# ============================================================================

ENDPOINT_SECURITY_CHECKLIST = """
Para cada novo endpoint que acessa dados:

□ Usar Depends(require_tenant_owner) para autenticação
  
□ Em TODA query, adicionar WHERE account_id == current_account.id:
  stmt = select(Model).where(Model.account_id == account.id)

□ Validar ownership antes de retornar dados:
  await TenantValidator.validate_account_ownership(
      data.account_id,
      current_account
  )

□ Registrar em auditoria (AuditLog):
  AuditLog.log_access(account.id, "action", "resource_type", resource_id)

□ Testar que usuário A não vê dados de usuário B

□ Testar que requests sem token são rejeitados
"""

# ============================================================================
# 3. QUERY PATTERNS SEGUROS
# ============================================================================

SAFE_QUERY_PATTERNS = """
// ✅ SEGURO: Query com filtro de tenant

from sqlalchemy import select, and_

# Pattern 1: Get owned resource
stmt = select(Subscription).where(
    Subscription.account_id == account.id
)

# Pattern 2: Join com filtro de tenant
stmt = select(Subscription).join(Account).where(
    and_(
        Subscription.account_id == account.id,
        Account.id == account.id
    )
)

# Pattern 3: Update owned resource
stmt = update(Subscription).where(
    Subscription.account_id == account.id
).values(status='confirmed')

# Pattern 4: Delete owned resource
stmt = delete(Subscription).where(
    Subscription.account_id == account.id
)

// ❌ INSEGURO: Query sem filtro
select(Subscription)  # Busca TUDO
select(Subscription).where(Subscription.id == id)  # Qualquer um pode acessar
"""

# ============================================================================
# 4. ROW-LEVEL SECURITY (RLS) NO POSTGRESQL
# ============================================================================

RLS_SETUP = """
Para máxima proteção, habilite RLS no PostgreSQL:

1. Execute os scripts em backend/app/core/rls_policies.py

2. Exemplos de RLS policies:

-- Cada account vê só suas subscriptions
ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;

CREATE POLICY subscriptions_isolation ON subscriptions
  USING (account_id = current_setting('app.current_account_id')::TEXT)
  WITH CHECK (account_id = current_setting('app.current_account_id')::TEXT);

3. Em cada request, configure o account_id:

from app.core.rls_policies import set_account_context

async def set_request_context(account_id: str, db: AsyncSession):
    # Executa função PostgreSQL
    await db.execute(
        text("SELECT set_account_context(:account_id)"),
        {"account_id": account_id}
    )
"""

# ============================================================================
# 5. ENCRIPTAÇÃO DE DADOS SENSÍVEIS
# ============================================================================

SENSITIVE_DATA_ENCRYPTION = """
Dados que DEVEM ser encriptados:

□ API Keys / Tokens
  - Usar Fernet (app.core.security.FERNET_KEY)
  - Nunca guardar em plain text
  
□ Senhas
  - Usar bcrypt (já implementado)
  - Nunca logarar
  
□ CPF/CNPJ
  - Encriptar se guardar
  - Validar origem
  
□ Dados de Pagamento
  - NUNCA guardar número de cartão
  - Usar tokenização do Asaas
  - Apenas armazenar asaas_payment_id

Exemplo seguro:
from cryptography.fernet import Fernet

class APIKeyService:
    @staticmethod
    def encrypt_key(key: str, fernet_key: str) -> str:
        f = Fernet(fernet_key)
        return f.encrypt(key.encode()).decode()
    
    @staticmethod
    def decrypt_key(encrypted: str, fernet_key: str) -> str:
        f = Fernet(fernet_key)
        return f.decrypt(encrypted.encode()).decode()
"""

# ============================================================================
# 6. AUDITORIA E LOGS
# ============================================================================

AUDIT_LOGGING = """
Registre TODAS as ações sensíveis:

from app.core.tenant_security import AuditLog

# Log de acesso a recurso
AuditLog.log_access(
    account_id="acc-123",
    action="view_subscription",
    resource_type="subscription",
    resource_id="sub-456"
)

# Log de evento de segurança
AuditLog.log_security_event(
    account_id="acc-123",
    event_type="unauthorized_access_attempt",
    severity="critical",
    details="IP: 192.168.1.1"
)

# Log de acesso a dados sensíveis
AuditLog.log_data_access(
    account_id="acc-123",
    endpoint="/api/v1/payments/current",
    ip_address="192.168.1.1"
)

Revisar logs regularmente para:
- Tentativas de acesso não autorizado
- Acessos a dados sensíveis
- Padrões anormais de acesso
- Possíveis vazamentos de dados
"""

# ============================================================================
# 7. TESTES DE SEGURANÇA
# ============================================================================

SECURITY_TESTS = """
Sempre teste isolamento de tenant:

import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_user_cannot_see_other_user_data(client: AsyncClient):
    # User A faz login
    token_a = await login(email="a@test.com", password="pass")
    
    # User B faz login
    token_b = await login(email="b@test.com", password="pass")
    
    # User A cria uma subscription
    resp_a = await client.post(
        "/api/v1/payments/subscribe",
        json={"plan": "pro"},
        headers={"Authorization": f"Bearer {token_a}"}
    )
    sub_id = resp_a.json()["id"]
    
    # User B tenta acessar a subscription de A
    resp_b = await client.get(
        f"/api/v1/payments/{sub_id}",
        headers={"Authorization": f"Bearer {token_b}"}
    )
    
    # Deve retornar 403 Forbidden, NÃO 404
    assert resp_b.status_code == 403
    
    # User A consegue acessar
    resp_a_own = await client.get(
        f"/api/v1/payments/{sub_id}",
        headers={"Authorization": f"Bearer {token_a}"}
    )
    assert resp_a_own.status_code == 200
"""

# ============================================================================
# 8. COMPLACÊNCIA LEGAL (CONFORMIDADE)
# ============================================================================

COMPLIANCE = """
Para evitar processos por vazamento de dados:

✅ LGPD (Lei Geral de Proteção de Dados - Brasil):
- Consentimento explícito para coletar dados
- Direito de acesso aos próprios dados
- Direito de exclusão ("direito ao esquecimento")
- Segurança adequada dos dados
- Notificação em caso de vazamento

✅ Implementar:
□ Isolamento multi-tenant
□ Encriptação de dados em repouso
□ Auditoria de acessos
□ Logs de deletação
□ Rate limiting contra brute force
□ HTTPS obrigatório
□ Senha forte obrigatória
□ 2FA opcional/obrigatório
□ Direito de exportação de dados
□ Direito de deletar conta

✅ Documentação:
□ Política de Privacidade
□ Termos de Serviço
□ Política de Retenção de Dados
□ Plano de Resposta a Incidentes
"""

# ============================================================================
# 9. REFERÊNCIAS
# ============================================================================

REFERENCES = """
- OWASP Multi-Tenant: https://cheatsheetseries.owasp.org/
- LGPD: https://www.gov.br/cidadania/pt-br/acesso-a-informacao/lgpd
- PostgreSQL RLS: https://www.postgresql.org/docs/current/ddl-rowsecurity.html
- SQLAlchemy Security: https://sqlalchemy.org/
- Fernet Encryption: https://cryptography.io/en/latest/fernet/
"""

__all__ = [
    'ENDPOINT_SECURITY_CHECKLIST',
    'SAFE_QUERY_PATTERNS',
    'RLS_SETUP',
    'SENSITIVE_DATA_ENCRYPTION',
    'AUDIT_LOGGING',
    'SECURITY_TESTS',
    'COMPLIANCE'
]
