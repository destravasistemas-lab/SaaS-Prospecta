"""
CHECKLIST DE SEGURANÇA MULTI-TENANT
Marque os itens antes de colocar em produção
"""

# ============================================================================
# SEGURANÇA DE DADOS
# ============================================================================

SECURITY_CHECKLIST = {
    "Database": [
        {
            "item": "✅ Row-Level Security (RLS) habilitado",
            "status": "TODO",
            "action": "Executar scripts em app/core/rls_policies.py",
            "risk": "CRITICAL"
        },
        {
            "item": "✅ Índices de tenant_id/account_id criados",
            "status": "TODO",
            "action": "Verificar migrations/alembic",
            "risk": "HIGH"
        },
        {
            "item": "✅ Backups diários configurados",
            "status": "TODO",
            "action": "Configurar pg_dump automático",
            "risk": "HIGH"
        },
        {
            "item": "✅ Soft-delete implementado",
            "status": "TODO",
            "action": "Adicionar deleted_at em modelos sensíveis",
            "risk": "MEDIUM"
        },
    ],
    "API Endpoints": [
        {
            "item": "✅ Todas as rotas usam require_tenant_owner",
            "status": "TODO",
            "action": "Auditar cada @router.get/post/put/delete",
            "risk": "CRITICAL"
        },
        {
            "item": "✅ Validação de account_id em toda query",
            "status": "TODO",
            "action": "Code review",
            "risk": "CRITICAL"
        },
        {
            "item": "✅ Sem informação sensível em logs públicos",
            "status": "TODO",
            "action": "Verificar logging.py",
            "risk": "HIGH"
        },
        {
            "item": "✅ Rate limiting implementado",
            "status": "TODO",
            "action": "Instalar slowapi",
            "risk": "MEDIUM"
        },
    ],
    "Autenticação": [
        {
            "item": "✅ JWT com expiração curta",
            "status": "TODO",
            "action": "Verificar JWT_ACCESS_EXPIRE_MINUTES",
            "risk": "HIGH"
        },
        {
            "item": "✅ Refresh tokens implementados",
            "status": "TODO",
            "action": "Verificar em auth_jwt.py",
            "risk": "MEDIUM"
        },
        {
            "item": "✅ Senhas com bcrypt (≥12 rounds)",
            "status": "TODO",
            "action": "Verificar security.py",
            "risk": "HIGH"
        },
        {
            "item": "✅ 2FA opcional para accounts premium",
            "status": "TODO",
            "action": "Implementar TOTP/SMS",
            "risk": "MEDIUM"
        },
    ],
    "Dados Sensíveis": [
        {
            "item": "✅ API Keys encriptadas com Fernet",
            "status": "TODO",
            "action": "Verificar meta_token_service.py",
            "risk": "CRITICAL"
        },
        {
            "item": "✅ CPF/CNPJ nunca em plain text",
            "status": "TODO",
            "action": "Encriptar se guardar",
            "risk": "CRITICAL"
        },
        {
            "item": "✅ Asaas payment_id tokenizado",
            "status": "TODO",
            "action": "Nunca usar direct payment access",
            "risk": "CRITICAL"
        },
        {
            "item": "✅ Tokens de acesso do Meta criptografados",
            "status": "TODO",
            "action": "Usar FERNET_KEY para encriptar",
            "risk": "CRITICAL"
        },
    ],
    "Auditoria": [
        {
            "item": "✅ Todos os acessos logados",
            "status": "TODO",
            "action": "Usar AuditLog.log_access()",
            "risk": "HIGH"
        },
        {
            "item": "✅ Eventos de segurança registrados",
            "status": "TODO",
            "action": "Usar AuditLog.log_security_event()",
            "risk": "HIGH"
        },
        {
            "item": "✅ Acesso a dados sensíveis logado",
            "status": "TODO",
            "action": "Usar AuditLog.log_data_access()",
            "risk": "MEDIUM"
        },
        {
            "item": "✅ Logs não podem ser deletados",
            "status": "TODO",
            "action": "CONSTRAINT CHECK em audit_logs",
            "risk": "CRITICAL"
        },
    ],
    "Comunicação": [
        {
            "item": "✅ HTTPS obrigatório em produção",
            "status": "TODO",
            "action": "Configurar em nginx/reverse proxy",
            "risk": "CRITICAL"
        },
        {
            "item": "✅ CORS restrito a domínios conhecidos",
            "status": "TODO",
            "action": "Configurar em settings.py",
            "risk": "HIGH"
        },
        {
            "item": "✅ Security headers implementados",
            "status": "TODO",
            "action": "Middleware com CSP, X-Frame-Options, etc",
            "risk": "MEDIUM"
        },
        {
            "item": "✅ SQL Injection protegido (SQLAlchemy ORM)",
            "status": "TODO",
            "action": "Nunca usar f-strings em SQL",
            "risk": "CRITICAL"
        },
    ],
    "Testes": [
        {
            "item": "✅ Teste: User A não vê dados de User B",
            "status": "TODO",
            "action": "pytest test_tenant_isolation.py",
            "risk": "CRITICAL"
        },
        {
            "item": "✅ Teste: Sem token = 401",
            "status": "TODO",
            "action": "pytest test_auth.py",
            "risk": "HIGH"
        },
        {
            "item": "✅ Teste: Token expirado = 401",
            "status": "TODO",
            "action": "pytest test_jwt.py",
            "risk": "HIGH"
        },
        {
            "item": "✅ Teste: SQL Injection",
            "status": "TODO",
            "action": "pytest test_sql_injection.py",
            "risk": "CRITICAL"
        },
        {
            "item": "✅ Teste: Brute force bloqueado",
            "status": "TODO",
            "action": "pytest test_rate_limiting.py",
            "risk": "MEDIUM"
        },
    ],
    "Infraestrutura": [
        {
            "item": "✅ Secrets em .env (não versionado)",
            "status": "TODO",
            "action": "Adicionar .env ao .gitignore",
            "risk": "CRITICAL"
        },
        {
            "item": "✅ Chaves rotacionadas regularmente",
            "status": "TODO",
            "action": "Plano de rotação mensal",
            "risk": "HIGH"
        },
        {
            "item": "✅ WAF (Web Application Firewall)",
            "status": "TODO",
            "action": "Cloudflare/AWS WAF",
            "risk": "MEDIUM"
        },
        {
            "item": "✅ Monitoramento ativo",
            "status": "TODO",
            "action": "Sentry/LogRocket",
            "risk": "MEDIUM"
        },
    ],
    "Conformidade": [
        {
            "item": "✅ Política de Privacidade em /privacy",
            "status": "TODO",
            "action": "Redigir com advogado",
            "risk": "LEGAL"
        },
        {
            "item": "✅ Termos de Serviço",
            "status": "TODO",
            "action": "Redigir com advogado",
            "risk": "LEGAL"
        },
        {
            "item": "✅ LGPD: Direito de acesso implementado",
            "status": "TODO",
            "action": "Endpoint /api/v1/data/export",
            "risk": "LEGAL"
        },
        {
            "item": "✅ LGPD: Direito de deletar implementado",
            "status": "TODO",
            "action": "Endpoint /api/v1/account/delete",
            "risk": "LEGAL"
        },
    ]
}

# ============================================================================
# COMANDOS PARA AUDITAR SEGURANÇA
# ============================================================================

AUDIT_COMMANDS = """
# 1. Verificar se RLS está habilitado
psql -U postgres -d adstudioai -c "
  SELECT schemaname, tablename, rowsecurity 
  FROM pg_tables 
  WHERE rowsecurity = true;"

# 2. Auditar queries sem filtro de account_id
grep -r "select(" backend/app/routes/ | grep -v "account_id"

# 3. Verificar secrets não versionados
git status | grep ".env"

# 4. Listar endpoints públicos (sem autenticação)
grep -r "@router" backend/app/routes/ | grep -v "Depends(require_tenant_owner)"

# 5. Procurar por f-strings em SQL
grep -r "f\"SELECT\\|f'SELECT" backend/app/

# 6. Verificar encriptação de dados sensíveis
grep -r "asaas_api_key\\|api_key\\|token" backend/app/models/ | grep -v "encrypted"

# 7. Rodar testes de segurança
pytest backend/tests/ -k "security or tenant or auth"

# 8. Verificar logs de acesso
tail -f logs/security.log | grep "SECURITY"
"""

# ============================================================================
# ROTEIRO DE IMPLEMENTAÇÃO
# ============================================================================

IMPLEMENTATION_ROADMAP = """
FASE 1: Isolamento de Dados (CRÍTICO - AGORA)
├── ✅ Validação de tenant_id em todas as queries
├── ✅ require_tenant_owner em todas as rotas autenticadas
├── ✅ Auditoria de acessos
└── ✅ Testes de isolamento

FASE 2: Criptografia de Dados (CRÍTICO - PRÓXIMA SEMANA)
├── Encriptar API Keys do Meta
├── Encriptar CPF/CNPJ
├── Encriptar tokens Asaas
└── Rotação de FERNET_KEY

FASE 3: Rate Limiting e DDoS (IMPORTANTE - 2 SEMANAS)
├── Rate limiting por IP
├── Rate limiting por account
├── CAPTCHA em login
└── WAF (Cloudflare)

FASE 4: LGPD e Conformidade (IMPORTANTE - 1 MÊS)
├── Endpoint de exportação de dados
├── Endpoint de deletar conta
├── Política de Privacidade
└── Termos de Serviço

FASE 5: Incident Response (ONGOING)
├── Plano de resposta a incidentes
├── Alertas de segurança
├── Backup e recovery
└── Teste de disaster recovery
"""

print(f"""
╔════════════════════════════════════════════════════════════════════════════╗
║                   CHECKLIST DE SEGURANÇA MULTI-TENANT                      ║
║                                                                            ║
║  Status geral: {'AGUARDANDO IMPLEMENTAÇÃO' if all(
    item['status'] == 'TODO' for category in SECURITY_CHECKLIST.values() 
    for item in category) else 'EM PROGRESSO'}                              ║
╚════════════════════════════════════════════════════════════════════════════╝
""")

for category, items in SECURITY_CHECKLIST.items():
    print(f"\n📋 {category}:")
    for item in items:
        status_icon = "✅" if item['status'] == "DONE" else "⏳"
        risk_color = "🔴" if item['risk'] == "CRITICAL" else "🟡" if item['risk'] == "HIGH" else "🟢"
        print(f"  {status_icon} {risk_color} {item['item']}")
        print(f"     → {item['action']}")
