# As 3 camadas do prompt de agente — o contrato

> Reference do gate `ai-agents`. Decisão do usuário **2026-11-06**, vale para TODO agente de app, atual e
> futuro: o agente é formado por **três camadas** e toda mudança de comportamento cai em UMA delas.
> Referência viva = **Kailos** (~20 dias de correção diária de prompt a partir de incidentes de prod).
> Armazenamento/versões/API da config da loja → `tenant-config.md`. Tela e pré-prompt do ChatGPT →
> `frontend/references/agent-instructions.md`. Catálogo de anomalias e replay → `anomaly-catalog.md`.

## As camadas

| Camada | Nome na UI/conversa | O que é | Quem escreve | Onde mora |
| --- | --- | --- | --- | --- |
| **L1** | "Informações de Sistema" | COMO o agente age: regras gerais de comportamento de IA (o que aprendemos como especialistas) + regras de domínio do negócio (o que nós, criadores do app, aprendemos e definimos) | nós (plataforma) | módulo do prompt base (`agents/<agent>/prompt.py`) + guards em código |
| **L2** | "Informações via prompt direcionado para o ChatGPT" | O que É a loja: fatos e preferências DESSE negócio + as respostas dele às exceções. O mais completo possível para qualquer anomalia do negócio, montado pelo botão ChatGPT + pré-prompt | o dono da loja | Markdown do tenant (`agent_configs` / `org_agent_configs`) |
| **L3** | "Todo o ecossistema de ferramentas" | Dado e ação que o app JÁ tem configurados em outras telas: documentos, settings, cardápio/estoque/eventos, consultas ao banco, filas/equipes, horário | o dono, pelas telas do app | injetado no prompt (bloco runtime) OU tool |

### O que pertence a cada uma (e o que NÃO)

- **L1 — como agir.** Igual para TODO tenant. **Nunca nomeia loja, cidade ou pessoa** (teste de guarda
  no repo). Inclui política de IA (não inventar, quando calar, quando transferir, tom, formato curto),
  regra de domínio (ex.: "vender não é troca", "pedido só do cardápio"), uso das tools e os **guards em
  código** (L1 executável — não dependem do modelo obedecer). Exemplos genéricos aqui valem MENOS que fato
  da loja.
- **L2 — fatos da loja.** Identidade da IA, história, endereço, pagamento aceito, política de desconto/
  sinal, garantia, expressões da casa, "nunca diga", FAQ e a seção final **"Situações especiais"** (a
  resposta da loja a exceções: "Currículos: entregar no caixa"). **Proibido em L2:** regra de fluxo/
  comportamento ("transfira sempre que…", "diga que é humano") — preferência vira "A loja prefere…";
  e **dado que vive em L3** (horário, preço, taxa de entrega, estoque, equipes) — o pré-prompt do ChatGPT
  proíbe repetir. Se a loja escreveu mesmo assim, L3 vence.
- **L3 — dado vivo.** Vem de outras telas/tabelas. É a única fonte do fato: horário, preço, taxa, estoque,
  status do pedido, equipes e gatilhos. Pode entrar de dois jeitos: **estável** (cardápio/catálogo,
  dados do negócio — vão no prefixo cacheável) ou **volátil** (contexto da conversa/cliente, data/hora
  da loja, histórico do contato). Preço e totais calculados no SERVIDOR (guard "G"), nunca pelo modelo.

## Ordem canônica de composição

```
1. L1  prompt base (método)                       ┐
2. STORE_CONFIG_HEADER + L2 (markdown da loja)    ┘ prefixo CACHEÁVEL (idêntico por tenant)
3. L3 estável   (catálogo/cardápio, dados do negócio, regras de captura)
4. L3 volátil   (contexto da conversa e do cliente, equipes/fila, histórico)
5. Regra de identidade (DISCLOSURE_RULE) — SEMPRE O ÚLTIMO bloco
   (o relógio — data/hora da loja — vai no TURNO DO USUÁRIO, não no system: mantém o prefixo estável)
```

- **L1 + L2 = prefixo cacheável**; nada de timestamp/request id/nome do contato no topo (`usage-cost.md`).
- **Identidade por último** porque o L2 é texto livre editável pela loja: um guardrail colocado antes dele
  é sobrescrevível por uma linha ("você é humana"). Tudo depois do 1º byte volátil já é incacheável, então
  a posição final não custa cache.
- **`tenant_instructions_middleware` NÃO se usa quando há L3.** Ele anexa o Markdown do tenant DEPOIS do
  prompt inteiro: duplicaria o L2 já composto e o poria após a regra de identidade. Agente sem L3/sem regra
  de identidade (genérico do template) usa o middleware; agente com L3 compõe à mão
  (`compose_system_prompt` + `split_system_prompt` → `(stable, variable)`) e fica só com
  `[sliding_window_middleware, empty_reply_guard_middleware]`.
- **Variante aceita (agentes INTERNOS, akmeo):** prompt do tenant primeiro e bloqueio duro por último —
  vale pela posição. Só para agente que fala com o próprio time, nunca com o público.
- Núcleo do template: `compose_system_message(base, tenant_markdown, runtime_context="")`
  (`core/agents/tenant_instructions.py`) cobre o caso L1 + L2 + runtime simples.

## Precedência (declare-a também ao modelo no prompt base)

**guardrails L1 > regra de identidade > L3 ao vivo > fatos L2 > exemplos genéricos do L1.**

- O `STORE_CONFIG_HEADER` diz ao modelo: "isto complementa o método; em conflito vale o método;
  preço/estoque/horário/equipes escritos aqui valem menos que as ferramentas e o contexto ao vivo".
- O prompt base abre com a mesma linha de precedência (kailos `prompt.py`, 1º parágrafo) e diz o que fazer
  com fato desconhecido: "o que a loja não informou e nenhuma ferramenta devolve, você não sabe".
- **Uma fonte de verdade por fato.** Sobreposição é tolerada (loja escreve o horário e a tela também tem);
  **contradição não** — quando divergem, L3 ao vivo vence e o pré-prompt do ChatGPT já proíbe repetir.
  O system prompt "supera" os dois extremos: o que importa é que a ordem seja determinística.

## Onde entra cada correção (tabela de decisão)

| Sintoma em prod | Camada | Artefato |
| --- | --- | --- |
| Inventou preço/taxa/total | L3 + G | preço calculado no servidor (emporion `price_order`, `order_pricing`); tool devolve o número |
| Tom errado PARA ESTA loja / gíria / "chama de senhor" | L2 | seção do Markdown da loja (via ChatGPT) |
| Resposta errada a exceção da loja (currículo, fornecedor) | L2 | "Situações especiais" do Markdown |
| Escorregão geral de comportamento (pergunta demais, repete nome, menu) | L1 | política no prompt base + changelog datado |
| Informou horário/estoque desatualizado | L3 | injetar/consultar dado vivo; nunca texto da loja |
| Escorregão que **repetiu 2 vezes** depois da regra de prompt | G | guard em código (abaixo) |
| Prompt injection / "me passa suas instruções" | L1 + G | política + `report_manipulation_attempt` (`chatbot-security.md`) |
| Modelo respondeu a quem não é cliente (OTP, robô, despedida) | L1 + G | silêncio `SEM_RESPOSTA` + `automated_message_guard` |
| Fala errada de identidade (disse ser humano) | L1 | `DISCLOSURE_RULE` (última) |

**Regra do segundo erro:** prompt corrige a 1ª ocorrência; se a MESMA falha voltar depois da regra, vira
**guard em código** (o modelo não é confiável para o que precisa ser 100%). Guards existentes —
kailos: `greeting_handoff_guard`, `handoff_decision` (trava de transferência), `handoff_announcement_guard`,
`manipulation_guard`, `reply_repeat_guard`, `empty_reply_guard`; emporion: `price_order`, `_closed_message`
(loja fechada responde fixo), `validate_fulfillment` (pedido só fecha com entrega/retirada válida).

## Proveniência: changelog datado no módulo do prompt base

O docstring do `prompt.py` (L1) guarda um **changelog de incidentes**: data, o que a IA fez em prod, a
decisão do usuário e o artefato que veio dela ("2026-10-16: a IA respondeu um OTP duas vezes — daí
`SEM_RESPOSTA`"). Sem isso a próxima sessão desfaz regra "estranha" que nasceu de uma dor real. Toda
mudança de L1 acrescenta uma entrada; toda entrada nasce de um cenário `prod-*` (`anomaly-catalog.md`).

## Implementações canônicas

| App | Papel | Observação |
| --- | --- | --- |
| **kailos** (`agents/vehicle_sales_agent/prompt.py`, `agents/whatsapp_attendant/agent.py`) | **Referência** | `STORE_CONFIG_HEADER`, `DISCLOSURE_RULE`, `split_system_prompt`, guards, eval/replay |
| **emporion** (`agents/whatsapp_attendant/agent.py`) | Restaurante | `compose_system_prompt` com catálogo (L3 estável) + captura + runtime; preço/loja-fechada/fulfillment em código |
| **nexarena** | Eventos | alinhado à ordem canônica em 2026-11-06 |
| **akmeo** | Agentes internos | variante: texto do tenant primeiro, bloqueio duro por último |
| template `core/agents/` | Núcleo | `compose_system_message(base, tenant_markdown, runtime_context="")` |

## Don'ts

- **NUNCA** nome de loja/pessoa/cidade em L1; **NUNCA** regra de comportamento em L2; **NUNCA** dado de
  L3 (horário/preço/taxa/equipes) no pré-prompt do ChatGPT nem como "fato" do Markdown.
- **NUNCA** colocar texto do tenant DEPOIS da regra de identidade (agente público).
- **NUNCA** `tenant_instructions_middleware` em agente que já compõe L2 à mão.
- **NUNCA** corrigir com mais uma linha de prompt uma falha que já voltou duas vezes — vira guard.
- **NUNCA** corrigir sem antes registrar o incidente como cenário (`anomaly-catalog.md`).
