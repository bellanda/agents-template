# Instruções de agente de IA — tela de configuração do tenant

> Reference do gate `frontend`. Vale para todo projeto em que o CLIENTE do SaaS configura o que um
> agente de IA diz ao cliente final dele (atendente de WhatsApp por org). Backend do agente e política
> de plataforma (disclosure, janela de 24h) → gate `integrations` (`meta-policy.md`,
> `human-handoff-queues.md`).

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

1. **Quem é:** plataforma, ramo, canal, nome da loja (vem do cache da org já carregada).
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

## Don'ts

- **NUNCA** formulário que compila Markdown, "modo guiado/avançado", nem preview lado a lado.
- **NUNCA** pedir no prompt do ChatGPT (ou aceitar no Markdown) dado que tem tela própria — horário,
  equipes, estoque. Fonte única: runtime.
- **NUNCA** `dangerouslySetInnerHTML`/parser caseiro para mostrar o salvo — Streamdown.
- **NUNCA** salvar religando a IA: ligar é o `ToggleCard`, com o portão de canal conectado.
