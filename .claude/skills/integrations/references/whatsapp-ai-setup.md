# Setup do módulo WhatsApp + IA — ordem, prontidão e "inativo = sem IA"

Fonte ÚNICA do contrato (decisão do usuário 2026-11-07, após a IA da NV Grill responder com o agente
"inativo" na tela). Vale para todo app com atendente de IA público no WhatsApp (hoje: kailos,
emporion; nexarena no formato "atendente de plataforma", §5). `settings-dialog.md`,
`agent-instructions.md` e `tenant-config.md` apontam para cá — não duplique a regra lá.

## 1. Ordem canônica (grupo "Primeiros passos" do hub `?settings=`)

```
Empresa → [pré-requisitos do domínio] → Membros → Equipes → Atendente de IA
        → WhatsApp Business → Templates do WhatsApp → Ligações
```

- **Pré-requisitos do domínio** = o que o runtime do agente lê e sem o qual ele responde errado
  (emporion: Entrega/retirada e Cardápio; kailos: o que o `_build_runtime_context` precisa).
- **Atendente de IA antes do número**: o número só é conectado depois que existe instrução e quem
  atenda (Equipes). **Templates e Ligações depois do número**: os dois exigem o WhatsApp conectado
  (aprovação de template é da WABA; Calling exige o número), então antes dele estariam sempre travados.
- A ordem do array = ordem da nav = ordem do tour. `SETTINGS_GROUPS` também é ordem: "Primeiros passos"
  é SEMPRE o primeiro grupo (emporion tinha `["Conexões", "Atendimento"]` e Ligações/WhatsApp
  apareciam em cima do modelo). Seções extras vão em grupos depois.
- Teste obrigatório `sections-config.test.ts`: a sequência dos Primeiros passos e "o array segue a
  ordem dos grupos" (canônico kailos).

## 2. Prontidão no backend — uma função, três consumidores

`GET /organizations/{org_id}/setup-readiness` (permissão de leitura do hub) →

```json
{
  "steps": [{ "id": "business", "label": "Dados da empresa", "done": true, "section": "business" }],
  "can_connect_whatsapp": false,
  "can_enable_agent": false,
  "missing_for_whatsapp": ["queues", "agent_instructions"],
  "missing_for_agent": ["agent_instructions"],
  "whatsapp_connected": false
}
```

- `services/setup/setup_readiness_service.py` (por app: os PASSOS são do domínio; a FORMA é esta).
  Cada passo é uma consulta barata ao que já existe (cadastro, catálogo, equipes com membro ativo,
  instrução salva) — nada de flag "concluído" gravada à mão.
- **Conectar o WhatsApp exige** todos os passos antes dele na ordem do §1 (empresa, domínio, ≥1
  equipe com ≥1 membro ativo, instrução salva não vazia).
- **Ligar o agente exige** a instrução salva + os mesmos pré-requisitos. **NÃO exige o número
  conectado**: liga antes e, quando o número conecta, ele já responde (o toggle diz "começa a
  responder quando o WhatsApp estiver conectado"). Desligar nunca é bloqueado.
- **Travas no servidor, não só na tela:** `PATCH …/agent-config/enabled {enabled:true}` e as rotas de
  conexão do número (Embedded Signup + token manual) chamam a mesma função e devolvem **409** com a
  lista do que falta (`detail` em pt-BR: "Antes de conectar o WhatsApp: cadastre uma equipe com
  membro…"). Conexão que já existe NUNCA é desfeita por essa regra; ela só barra a nova. Org com
  número `active` (`whatsapp_connected`) pode RECONECTAR (renovar token, trocar número) mesmo com
  um passo regredido depois (membro saiu, instrução apagada).
- **Front:** hook `useSetupReadiness(orgId)` (TanStack Query, `["setup-readiness", orgId]`,
  invalidado pelos saves que mudam um passo). Consumidores:
  - **nav do hub**: ✓ no passo feito, cadeado no bloqueado — a seção bloqueada ABRE normal e mostra
    o que falta (nunca item desabilitado sem explicação). Número conectado = ✓ no WhatsApp e nenhum
    cadeado em WhatsApp/Templates/Ligações (NV Grill 2026-11-07: conectada, instrução em branco);
  - **`WhatsAppReadinessCard`** na seção WhatsApp: lista ✓/✗ com "Configurar" por item e o botão de
    conectar DESABILITADO até `can_connect_whatsapp` (antes era só aviso);
  - **`ToggleCard` do atendente**: desabilitado + dica do que falta até `can_enable_agent`;
  - checklist do dashboard (emporion `OnboardingChecklist`) lê o mesmo endpoint (antes recalculava).

## 3. "Inativo = sem IA" — semântica do runtime

O atendente é considerado **ativo** só quando `row and row.enabled and instrução.strip()`:

| Estado | Tela | Runtime |
| --- | --- | --- |
| Sem linha em `org_agent_configs` | Desativado | **inativo** → humano, motivo `ai_not_configured` |
| `enabled=false` | Desativado | inativo → humano, `ai_disabled` |
| `enabled=true` + instrução em branco | (o toggle não deixa) | inativo → humano, `ai_not_configured` |
| `enabled=true` + instrução | Ativo | ativo |

- `get_runtime_config` devolve `enabled = bool(row and row["enabled"] and configured)`; dispatcher e
  follow-up leem `runtime.get("enabled", False)` — **default False em todo lugar**. Incidente
  emporion 2026-11-06: `row["enabled"] if row else True` + `get("enabled", True)` fizeram a IA
  responder sem instrução enquanto a tela mostrava "Desativado" (o kailos tinha corrigido em
  2026-09-18 e a correção não foi propagada).
- `PUT` (salvar instrução) **não muda** o `enabled` e o schema não tem default `True`; ligar é só o
  toggle.
- **Inativo não chama o Haiku para atender:** turno, follow-up e leitura de imagem do cliente ficam
  parados. Continuam (servem ao humano ou são ação do admin — documente no app se acrescentar outro):
  transcrição de áudio (Whisper, o inbox mostra o texto), OCR do cardápio no upload, relatório
  diário, sugestão de ritmo de campanha, revisão de espera do cliente.
- Teste de regressão obrigatório: org sem linha / `enabled=false` / instrução em branco → a fábrica
  do modelo (`init_model`/`create_agent`) NUNCA é chamada e a conversa vai para humano.

## 4. Cache

O runtime cacheia a config (Valkey, TTL curto); save, toggle e restore invalidam. Default do cache
ausente = inativo, nunca ativo.

## 5. Atendente de plataforma (nexarena)

Um número e um agente da plataforma, sem hub por org: `platform_agent_configs.enabled BOOLEAN NOT
NULL DEFAULT false` (migration com `UPDATE … SET enabled = true WHERE system_prompt_markdown <> ''`
para não desligar prod), `ToggleCard` "Atendente ativo" na tela do superusuário (travado sem
instrução), runtime = `settings.agent.enabled` (chave de emergência do yaml) **E** a linha ativa com
instrução. Mesma tabela do §3.
