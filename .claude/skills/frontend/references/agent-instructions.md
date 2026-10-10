# Instruções de agente de IA — tela de configuração (Markdown + ChatGPT + versões)

> Reference do gate `frontend`. Vale para **todo app com agente de IA configurável** — o CLIENTE do
> SaaS configura o que um agente diz/faz (atendente de WhatsApp por org no kailos/balizap; agentes de
> anúncios por org no akmeo; agente da plataforma no nexarena). Decisão de **2026-10-01**: UM
> desenho em todos os apps. Backend do agente e política de plataforma (disclosure, janela de 24h) →
> gate `integrations` (`meta-policy.md`, `human-handoff-queues.md`); gate `ai-agents`
> (`tenant-config.md`).

## Canônico (onde copiar)

Template `~/code/github-templates/agents-template/frontend/src/components/agent-config/` — **copie
por inteiro** para o app (cada app vendora; não importe entre repos):

| Arquivo                      | Papel                                                                                          |
| ---------------------------- | ---------------------------------------------------------------------------------------------- |
| `AgentConfigScreen.tsx`      | Tela: seletor de agente (quando há vários) + `InstructionsCard` + `VersionsPanel`              |
| `InstructionsCard.tsx`       | Passos 1-2-3, botão do ChatGPT, textarea mono, contador, Salvar nova versão; leitura = preview |
| `MarkdownPreview.tsx`        | Renderiza o Markdown salvo (Streamdown) com o ritmo tipográfico da tela                        |
| `VersionsPanel.tsx`          | Histórico (`vN`, Atual, nota, data) + Restaurar (cria versão nova)                             |
| `chatgpt-builder-prompt.ts`  | Pré-prompt do ChatGPT — **o único lugar** que sabe o que o runtime já injeta                   |
| `use-agent-config.ts`        | Queries/mutations de config e versões (`setQueryData` antes do `invalidateQueries`)            |

Origem: balizap `agent-config/*` (estrutura) + `chatgpt-builder-prompt` do **kailos** (o mais
completo: recebe `ChatGptStoreFacts` — nome, cidade, endereço, telefone já cadastrados — para o
ChatGPT não perguntar de novo, e lista tudo que o runtime injeta). `AgentTester`, `DocumentAiConfig`
e `ModelSetup` do balizap são **extras do balizap**, não fazem parte do padrão.

**Onde monta:** seção "Atendente de IA" do hub de Settings (kailos/balizap — `settings-dialog.md`);
página `/o/$id/agents/$agentId` com abas (akmeo — vários agentes por org); **área de superusuário**
no nexarena (agente da plataforma: 1 número monitorado por superusuários, **sem Equipes**, com
tabela de config/versões da plataforma — modelo do `tenant_agent_configs` do template, sem tenant).
O **preview** é o modo de leitura do texto salvo (renderizado) — não um painel lateral ao vivo.

## O contrato em uma frase

**Um Markdown só, montado no ChatGPT, colado, salvo e mostrado renderizado.** Sem formulário que
compila Markdown, sem "modo guiado / modo avançado" (nem os termos), sem preview lateral.

Por quê: o formulário guiado cobria 6 campos e o lojista precisava de 20; o modo avançado virava a
fonte da verdade na primeira edição e o formulário mentia dali em diante. O ChatGPT entrevista melhor
do que qualquer wizard, e o que volta é exatamente o texto que vai para o prompt.

## Anatomia

```
[ ToggleCard  Atendente IA · Ativo/Desativado ]      PATCH /enabled — nasce DESLIGADO; ligar
                                                     exige o canal conectado (senão 400 + atalho)
┌ Instruções do atendente ─────────────── [Editar] ┐
│ (salvo)   Markdown renderizado (Streamdown)       │
│ (editando)                                        │
│   1. Clique em Montar com o ChatGPT e responda…   │  passos = 1 coluna (sequencial), max-w-2xl
│   2. No fim, ele entrega um texto pronto. Copie.  │
│   3. Cole abaixo e clique em Salvar nova versão.  │
│   [ Montar com o ChatGPT ↗ ]                      │  <a target="_blank" rel="noopener noreferrer">
│   ┌ textarea mono, largura total ──────────────┐  │
│   └────────────────────────────────────────────┘  │
│   1.234 de 20.000 caracteres                      │  mesmo teto do backend
│                      [Cancelar] [Salvar nova versão]  Cancelar só quando já há versão salva
└───────────────────────────────────────────────────┘
[ Histórico de versões ]  StaticDataList: vN · Atual · nota · data · Restaurar
```

- Começa **editando** quando não há texto salvo; senão, em leitura.
- O card monta com **`key={activeVersion}`**: salvar ou restaurar remonta já em leitura com o texto
  novo; um save que falhou não remonta e o rascunho fica na tela.
- A mutation de salvar/restaurar faz `setQueryData(configKey, resposta)` **antes** do
  `invalidateQueries` — senão o refetch mostra a versão anterior renderizada por um instante.
- "Salvar" desabilitado com texto vazio, acima do teto ou igual ao salvo.
- Renderizado com o `MessageResponse` (Streamdown) do projeto — nunca parser de Markdown caseiro.

## O botão do ChatGPT

```ts
const CHATGPT_URL = "https://chatgpt.com/";
export function buildChatGptBuilderUrl(storeName: string): string {
  return `${CHATGPT_URL}?prompt=${encodeURIComponent(builderPrompt(storeName.trim()))}`;
}
```

É navegação, não `fetch`: nenhuma diretiva de CSP muda. O prompt mora num arquivo por projeto
(`agent-config/chatgpt-builder-prompt.ts`) e carrega, nesta ordem:

1. **Quem é:** plataforma, ramo, canal e **o que o cadastro da org já sabe** (nome, cidade, endereço,
   telefone — vem do cache da org já carregada; o ChatGPT não pergunta de novo).
2. **O que a plataforma JÁ injeta — "não pergunte nem escreva nada a respeito":** o prompt-base
   (triagem, guardrails de preço/troca), a regra de identidade, e tudo que tem tela própria e entra em
   runtime (horário comercial, equipes e seus gatilhos, catálogo/estoque, data e hora). Repetir isso no
   Markdown cria duas fontes que divergem na primeira edição de uma delas.
3. **A entrevista:** 3 a 5 perguntas por vez, esperando a resposta; lista numerada do que cobrir.
4. **"Se eu pular algo, deixe de fora. Nunca invente dado da loja."**
5. **A entrega:** UM bloco de código Markdown com títulos fixos, o de topo igual ao nome que o
   prompt-base usa para o bloco do tenant (ex.: `## CONFIGURAÇÃO DA LOJA`); segunda pessoa, frases
   curtas.

Mantenha a URL codificada abaixo de ~4 mil caracteres (acento vira 6, espaço vira 3).

### Método da plataforma × fatos da loja (kailos, 2026-10-09)

O texto do tenant é **complementar**, nunca substituto. Separação canônica:

- **Prompt-base da plataforma ("método")**: COMO a IA atende — qualificação, técnicas, objeções,
  guardrails, uso das tools, QUANDO transferir. Igual para toda loja: **zero nome de loja/pessoa**
  (teste de guarda). Kailos: `backend/agents/vehicle_sales_agent/prompt.py`.
- **Markdown do tenant ("fatos")**: identidade da IA, história, endereço, pagamento/bancos, troca,
  garantia, política de desconto/sinal, serviços, expressões da casa, FAQ, "nunca diga". A entrevista
  do ChatGPT pergunta SÓ isso e proíbe regra de comportamento ("transfira sempre que…", "diga que é
  humana"); preferência vira "A loja prefere…".
- **Composição**: o Markdown entra embrulhado num cabeçalho fixo de precedência (`STORE_CONFIG_HEADER`:
  "complementa o método; em conflito vale o método; preço/estoque/horário/equipes do texto valem menos
  que tools e contexto ao vivo"), depois o runtime, e a regra de identidade por último.
- **Equipes**: o gatilho da fila diz PARA QUEM; o método diz QUANDO. O bloco de equipes do runtime
  diz isso explicitamente — gatilho largo da loja ("transfira sempre que houver intenção de compra")
  causou handoff no primeiro "oi" em prod.
- **Calibração**: cenários reais anonimizados + replay contra o modelo real com tools falsas que
  espelham o schema das reais (`agents/vehicle_sales_agent/eval/`), fora do check.sh.

## Backend

- `PUT …/agent-config` recebe `{ system_prompt_markdown, enabled, note }` com `max_length` (o texto
  vai inteiro em TODA resposta da IA — colar uma conversa inteira por engano multiplica o custo).
- O save **tira a cerca de código que envolve o texto todo** (o "copiar" do ChatGPT às vezes leva
  junto): `^(`{3,})[\w-]*[ \t]*\r?\n(.*?)\r?\n\1[ \t]*$` com `DOTALL`. Cerca no meio é conteúdo.
- Cada save = linha imutável em `*_versions`; **restaurar é um save novo** que mantém o `enabled`
  corrente (o snapshot guarda o texto, não a decisão de estar no ar).
- Texto em branco = **não configurado**: o runtime devolve `enabled=false` e a conversa vai para humano.
- A regra de identidade do agente vai **depois** do Markdown do tenant na composição do prompt
  (`meta-policy.md`) — o texto é livre e pode tentar contradizê-la.

## Agente com TOOLS — as ferramentas são PERMISSÕES (akmeo)

Agente que age (chama ferramentas) não decide "o que pode fazer" num formulário de Selects por
linha: é **concessão de permissão**, e a UI reaproveita o picker de duas colunas de permissões
(akmeo `members/PermissionPickerColumns.tsx` — exporta `ColumnShell`/`DirectionChevron`/`EmptyRow`/`Direction`
— reutilizado por `agents/ToolPickerColumns.tsx` (`ToolColumn`: linha de ferramenta + toggle "Com aprovação"
= `GrantMode`) e pelo estado puro `agents/tool-picker.ts` (`ToolModes`, `groupTools`, `toolMatches`,
`modesFromItems`, `grantsFromModes`, `modesDiffer`). `agents/AgentToolsPanel.tsx` monta as duas colunas
no lugar dos antigos Selects por linha).

```
┌ Disponíveis ────────────┐   ┌ Permitidas ─────────────────────────────┐
│ [ buscar ferramenta… ]  │   │ [ buscar… ]                              │
│ ▸ Anúncios (3)          │ → │ ▸ Anúncios (2)                           │
│   Ler campanhas      →  │   │   Pausar campanha   [ Com aprovação ⊙ ]  │
│   Pausar campanha    →  │ ← │   Ajustar orçamento [ Com aprovação ⊙ ]  │
└─────────────────────────┘   └──────────────────────────────────────────┘
```

- Itens = catálogo de tools do **backend** (`key`, `group`/`groupPt`, `labelPt`, `descriptionPt`,
  `writes`, `risk`) agrupados por domínio — mesma regra de `permissions-display.md`; **busca
  obrigatória** (local, NFD+lower); badges "Escreve"/"Alto risco" no item.
- Clique move entre colunas (chevron de direção). Modo na coluna **Permitidas**: padrão `allow`;
  **"Com aprovação"** (`require_approval`) é um **toggle compacto na linha**, só habilitado para tool
  que `writes` fora do app (leitura pendente de aprovação humana não faz sentido). Exceção sancionada
  do 8a: linha densa de picker, não card. Fora de Permitidas = `deny` (não vai ao `bind_tools`).
- Salva com `DirtyBottomBar`/Salvar o **estado final** (o que não está na lista é revogado). Nível de
  autonomia "Analisar" mostra aviso: mesmo liberada, nenhuma tool de escrita é entregue ao modelo.
- Layout: `grid min-h-0 flex-1 gap-4 md:grid-cols-2` (mesma grade do dialog de permissões de
  membros) — abaixo de 768px as colunas empilham, Disponíveis acima de Permitidas.

## Templates, criação e o que o runtime lê (akmeo)

- **Templates de agente moram no CÓDIGO** (app-owned, ex.: `services/agents/templates.py`), cada um
  com **um** `instructions_markdown` (não mais N seções compiladas). A org cria agente **a partir de
  template (cópia)** ou **do zero** (UI "Novo agente" → `useCreate`) e edita livremente o seu.
- Editar = texto Markdown + ChatGPT (pré-prompt do domínio do agente, ex.: anúncios) + preview +
  limite de caracteres (mesmo teto do backend) + versões.
- **O runtime lê a VERSÃO ATIVA** — texto, concessões de tools e `extra_context` do snapshot
  imutável — **nunca** o estado "ao vivo" que a tela está editando. (Bug do akmeo tratado na
  padronização de 2026-10-01: `runner.py` lia grants/`extra_context` ao vivo, então edição em
  rascunho vazava para a próxima execução.) Migration compila as `sections` antigas em `system_prompt_markdown` em `agents`
  **e** `agent_versions` e só então remove `sections`/`markdown_overridden`/`prompt_compiler`.

## Don'ts

- **NUNCA** formulário que compila Markdown, "modo guiado/avançado", nem preview lado a lado.
- **NUNCA** pedir no prompt do ChatGPT (ou aceitar no Markdown) dado que tem tela própria — horário,
  equipes, estoque. Fonte única: runtime.
- **NUNCA** `dangerouslySetInnerHTML`/parser caseiro para mostrar o salvo — Streamdown.
- **NUNCA** salvar religando a IA: ligar é o `ToggleCard`, com o portão de canal conectado.
- **NUNCA** um editor de agente por app — copie o `agent-config/` do template; o que muda por app é o
  `chatgpt-builder-prompt.ts` (domínio) e o `use-agent-config.ts` (endpoints).
- **NUNCA** Select por linha para conceder tool a agente — é o picker de colunas (tools = permissões).
- **NUNCA** o runtime do agente ler config/grants "ao vivo" — sempre a versão ativa.
