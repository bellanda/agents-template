# RBAC — funções personalizadas e granularidade de permissão

Decisão do usuário 2026-11-17 (rodada Marcelo/Nery): toda loja cria suas próprias funções, e as
permissões são granulares o bastante para que "preparador" veja só Serviços. Vale para os apps com
RBAC por organização (kailos, akmeo, emporion, promoservice; nexarena/optimuslar têm modelo próprio).

## 1. Formato — `organizations.custom_roles` (JSONB)

```json
{ "preparador": { "label": "Preparador", "description": "Lava e prepara os carros",
                  "permissions": ["vehicle:read", "vehicle:services"], "based_on": "vendedor" } }
```

- Chave = slug do rótulo (minúsculas, ASCII, `_`, ≤40). **Imutável** depois de criada: membros
  (`organization_members.roles`) e convites pendentes (`organization_invites.roles`) a referenciam.
- `based_on` = chave de uma função PADRÃO (de onde foi copiada; copiada de outra personalizada
  herda o `based_on` dela). Quem agrupa por papel (ranking/TV de vendedor) usa
  `papel padrão OU função personalizada com based_on = <papel>`, nunca o literal.
- Antes de 2026-11-17 era `{key: [perms]}`; a migration `20261117100000_custom_roles_definition_shape`
  converte (label = chave em Title Case, `based_on` nulo; idempotente, `down` volta à lista).
- Leitor único das permissões: `resolve_membership_permissions` (canônico em
  `shared-backend/canonical/permission_service.py`) e `AuthContext.effective_permissions`
  (`models/auth/auth_context_jsonb.py`, por app). **Todo** código que lê `custom_roles` passa por
  eles — nada de `custom_roles[key]` direto como lista.

## 2. API (kailos; os outros apps portam igual em `routes/organizations/admin.py`)

Prefixo `/api/v1/organizations/admin/{org_id}/roles`:

| Verbo | Rota | Guard | Resposta |
| --- | --- | --- | --- |
| GET | `/roles` | `member:read` | `[{key,label,description,permissions,is_default,based_on,member_count}]` — padrão primeiro (ordem canônica, label = `RoleInfo.pt`), depois personalizadas por rótulo |
| POST | `/roles` `{label,description?,permissions,based_on?}` | `role:manage` | 201 + item; chave = slug do rótulo; colisão com padrão/existente → 409 |
| PATCH | `/roles/{key}` `{label?,description?,permissions?}` | `role:manage` | item; chave não muda; função padrão → 403 |
| DELETE | `/roles/{key}` | `role:manage` | 204; em uso por membro ou convite PENDENTE → 409 com `detail` listando (nome + id; e-mail do convite); padrão → 403; inexistente → 404 |

Lógica em `services/organizations/custom_role_service.py` (slug, validação, escalada), SQL em
`organization_repository` (`lock_custom_roles` = `SELECT … FOR UPDATE`, serializa as escritas do
JSONB) e nos repos de membro/convite. Auditoria: `organization.role_created|updated|deleted`
(ação nova exige enum + CHECK de `audit_events` na mesma migration).

## 3. Escalada de privilégio (mesma regra do `_validate_grant`)

- Permissão desconhecida → 422. Superusuário = catálogo inteiro.
- Criar/editar: `permissions ⊆ permissões efetivas do chamador`; senão 403.
- Editar/excluir: o chamador precisa ter TODAS as permissões atuais da função.
- Atribuir função a membro/convite continua em `_validate_grant` (aceita chave personalizada;
  permissões resultantes ⊆ as do chamador). Trava de último gestor segue no literal `admin`.
- `role:manage` está no catálogo, logo em todo papel construído de `PermissionScope` inteiro (Gestor).

## 4. Invalidação de cache

O trigger `organizations_custom_roles_auth_invalidate` (`notify_auth_invalidate_org_members`) faz
`NOTIFY auth_invalidate` para cada membro quando `custom_roles` muda; o `AuthContext` cacheado no
Valkey cai e a próxima request relê. Não reimplemente: escrever no JSONB basta (teste:
`tests/organizations/test_custom_roles_crud.py`).

## 5. Granularidade — as 9 regras ao criar/auditar permissão

1. **Aba de detalhe = chave própria** (preço, recebimento, serviços, histórico…): quem vê só uma aba tem só aquela chave.
2. **Seção de configuração = chave própria** (nada de `org:settings` guarda-chuva).
3. **Ação sensível separada**: dinheiro/contrato (termos, aprovar pagamento), destrutiva (excluir, cancelar negócio), LGPD/export (apagar, anonimizar, CSV, log de auditoria).
4. **`approve`/`execute` ≠ `manage`**: aprovar/executar não implica configurar, e vice-versa.
5. **Próprio × todos** (`*_own` × `*_all`/`read_all`): ver o que é seu ≠ ver tudo.
6. **Espelho front/back**: a mesma chave guarda a rota no backend e o `can()`/`beforeLoad`/item de menu no front; teste de contrato casa os dois.
7. **Papel nunca é guard**: nada de `roles.includes("admin")`/`isAdminLevel ||`; guard é permissão. Agrupar por papel (ranking) usa `based_on`.
8. **Leitura ≠ escrita**: o verbo (último segmento) decide o bloqueio por assinatura vencida (`READ_ONLY_PERMISSION_VERBS`, allow-list fail-closed); verbo novo nasce bloqueado.
9. **Divisão não muda acesso de ninguém**: chave nova é expandida em toda função padrão que cobria a antiga (e em `custom_roles`, `permissions_override`, convites pendentes). Só função nova (ex.: Preparador) traz acesso novo.

## 6. Padrão de migration de "chave dividida"

Dividir `old:key` em `new:a`, `new:b`… = uma migration de dados (dbmate, DEPOIS da de formato):

1. `DEFAULT_ROLES` no código recebe as chaves novas onde a antiga estava; a antiga sai do catálogo (ou fica, se ainda guarda algo).
2. SQL expande, para cada função em `organizations.custom_roles -> key -> 'permissions'`, cada `organization_members.permissions_override` e cada `organization_invites.permissions_override` (pendentes) que contém `old:key`: remove-a e adiciona as novas (`DISTINCT`, ordem estável). Escreva para o formato novo do JSONB e seja idempotente.
3. `down` reverte só o que for seguro (junta as novas na antiga se TODAS presentes).
4. **Teste de paridade**: aplicar a expansão às funções antigas (fixture com `old:key`) = as funções novas; e o conjunto efetivo de permissões de cada papel padrão antes/depois é idêntico (exceto funções novas).
5. Guards de rota e `can()` do front trocam para as chaves novas no mesmo PR; `test_route_protection` e o espelho front/back do catálogo continuam verdes.
