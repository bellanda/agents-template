---
paths:
  - "backend/agents/**"
  - "backend/src/api/core/agents/**"
  - "backend/src/api/**/agents/**"
  - "frontend/src/components/ai-elements/**"
  - "frontend/src/components/chat/**"
  - "frontend/src/components/agent-config/**"
---

# AI Agents — stack única (decisão do usuário, 2026-09-30)

**Todo projeto usa exatamente esta stack. Sem exceção, sem "só neste app".**

**Skill `ai-agents` (PORTÃO):** invoque ANTES de escrever qualquer chamada de LLM, agente/tool/subagente, chat com streaming, UI de IA (ai-elements/chat/agent-config), mídia/OCR, custo por tenant, config de agente do tenant, ou de propagar o template — ele traz a tabela "qual ferramenta usar" (one-shot vs structured vs agente vs subagente), o checklist e as references. Esta rule fixa a stack; o skill é o "como".

| Modalidade                                      | Provedor   | Modelo                                                |
| ----------------------------------------------- | ---------- | ----------------------------------------------------- |
| Texto (chat, tools, extração, classificação)    | OpenRouter | **GLM 5.3 Flash** — `Models.OpenRouter.GLM_5_3_FLASH` |
| Imagem (entender imagem, OCR, documento visual) | OpenRouter | **GLM 5.3 Flash** (mesmo modelo, multimodal)          |
| Vídeo                                           | OpenRouter | **GLM 5.3 Flash**                                     |
| Áudio (transcrição)                             | Groq       | **Whisper** `whisper-large-v3-turbo`                  |

- **Fonte canônica:** `~/code/github-templates/agents-template` — `backend/src/api/core/agents/` (`custom_providers.py`, `models.py`, `media.py`, …) e `backend/agents/`. Mudança na estrutura de agentes nasce **no template** e é propagada com `backend/scripts/sync_agents_to_another_fastapi_project.py`. Melhoria feita num app → leve de volta ao template.
- **Proibido:** DeepSeek, Gemini/`google-genai`, OpenAI direto, Anthropic direto, Novita, Ollama, Cerebras, Chutes, NVIDIA etc. — nem no registry, nem em `Settings`, nem no `.env.example`, nem como dependência. O client `langchain-openai` apontado pro base URL do OpenRouter é o único client de chat.
- **Secrets:** só `OPENROUTER_API_KEY` e `GROQ_API_KEY` (este só se o app recebe áudio). Resto (modelo, timeouts, flags) é config no `config/app/*.yaml`.
- **Model picker / catálogo por tenant:** oferece só GLM 5.3 Flash. Linha legada com outro slug → migration dbmate reescrevendo pro slug do GLM (precedente: balizap `20260909160000_default_model_glm_5_3_flash.sql`).
- **Não use sem uso:** app sem fluxo de áudio não carrega `media.py`/Groq; chave/campo/dependência sem leitor é apagado.
