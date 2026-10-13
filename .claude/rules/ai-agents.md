---
paths:
  - "backend/agents/**"
  - "backend/src/api/core/agents/**"
  - "backend/src/api/**/agents/**"
  - "frontend/src/components/ai-elements/**"
  - "frontend/src/components/chat/**"
  - "frontend/src/components/agent-config/**"
---

# AI Agents — stack única (decisão do usuário, 2026-09-30; modelo trocado para Claude Haiku 5.5 em 2026-10-10)

**Todo projeto usa exatamente esta stack. Sem exceção, sem "só neste app".**

**Por que Haiku 5.5 (bake-off 2026-10-10, 144 conversas simuladas com a config real da Promocar, julgadas às cegas):** Haiku `low` ≈ metade do custo do GLM high (US$3,5 vs 6,3 por mil conversas), mesma latência (p50 ~5s, p90 ~8,7s), 6–9x menos fatos inventados. Efforts maiores são lentos demais para WhatsApp (medium p90 12s, xhigh p90 28s, max p50 79s) — effort fica `low`. GLM saiu da stack (não fica no registry).

**Skill `ai-agents` (PORTÃO):** invoque ANTES de escrever qualquer chamada de LLM, agente/tool/subagente, chat com streaming, UI de IA (ai-elements/chat/agent-config), mídia/OCR, custo por tenant, config de agente do tenant, ou de propagar o template — ele traz a tabela "qual ferramenta usar" (one-shot vs structured vs agente vs subagente), o checklist e as references. Esta rule fixa a stack; o skill é o "como".

| Modalidade                                      | Provedor   | Modelo                                                                                                                                                 |
| ----------------------------------------------- | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Texto (chat, tools, extração, classificação)    | OpenRouter | **Claude Haiku 5.5**, effort `low` — `Models.OpenRouter.CLAUDE_HAIKU_5_5` (`anthropic/claude-haiku-5.5`)                                               |
| Imagem (entender imagem, OCR, documento visual) | OpenRouter | **Claude Haiku 5.5** (mesmo modelo, multimodal)                                                                                                        |
| Vídeo                                           | OpenRouter | **Claude Haiku 5.5** lendo QUADROS: o Haiku não aceita vídeo; `media.py` amostra 6 quadros com OpenCV e manda como imagens (o áudio do vídeo se perde) |
| Áudio (transcrição)                             | Groq       | **Whisper** `whisper-large-v3-turbo` (inalterado)                                                                                                      |

- **PDF:** o Haiku aceita PDF inline, mas o caminho continua MarkItDown/`ocr.py` (`supports_pdf_input=False`) até decisão testada.
- **Upstreams fixos EUA:** `provider_order=("anthropic", "amazon-bedrock/us-east-1", "google-vertex/us")`, `allow_fallbacks=False` — jurisdição declarada à Meta/política de privacidade, não preço. Não relaxe.
- **tool_choice:** o metadata do OpenRouter diz `supports_tool_choice.required/function=false` para todos os upstreams do Haiku, mas na prática `function_calling` forçado funciona (anthropic e bedrock testados). Teste com chamada real antes de mexer na ordem dos upstreams.
- **Cache de prompt:** SÓ com `cache_control: {type: ephemeral}` no topo do body (flag `prompt_cache_control=True` no `ModelConfig`, aplicada pelo `init_model`). Leitura em cache = 10% do preço; escrita = 125%. Prefixo estável continua obrigatório.
- **Preço:** US$0,10 entrada / 0,50 saída / 0,01 cache read / 0,125 cache write por 1M. Tokenizer gera ~1,6x mais tokens que o GLM para o mesmo texto.

- **Fonte canônica:** `~/code/github-templates/agents-template` — `backend/src/api/core/agents/` (`custom_providers.py`, `models.py`, `media.py`, …) e `backend/agents/`. Mudança na estrutura de agentes nasce **no template** e é propagada com `backend/scripts/sync_agents_to_another_fastapi_project.py`. Melhoria feita num app → leve de volta ao template.
- **Proibido:** DeepSeek, Gemini/`google-genai`, OpenAI direto, Anthropic DIRETO (SDK `anthropic`/`langchain-anthropic` — o acesso ao Claude é só via OpenRouter), GLM, Novita, Ollama, Cerebras, Chutes, NVIDIA etc. — nem no registry, nem em `Settings`, nem no `.env.example`, nem como dependência. O client `langchain-openai` apontado pro base URL do OpenRouter é o único client de chat.
- **Secrets:** só `OPENROUTER_API_KEY` e `GROQ_API_KEY` (este só se o app recebe áudio). Resto (modelo, timeouts, flags) é config no `config/app/*.yaml`.
- **Model picker / catálogo por tenant:** oferece só **Claude Haiku 5.5** (label "Claude Haiku 5.5"). Linha legada com outro slug (inclusive GLM) → migration dbmate reescrevendo para `anthropic/claude-haiku-5.5` (precedente: agents-template `20261010200000_default_model_claude_haiku_5_5.sql`).
- **Não use sem uso:** app sem fluxo de áudio não carrega `media.py`/Groq; chave/campo/dependência sem leitor é apagado.
