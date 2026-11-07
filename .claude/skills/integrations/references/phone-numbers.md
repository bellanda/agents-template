> Reference do gate `integrations` — telefone canônico da frota (decisão do usuário 2026-10-29:
> "garanta uma padronização de números em todas as interfaces de todos os apps"). Vale para TODO
> telefone de pessoa/empresa, com ou sem WhatsApp. Canônico = kailos.

# Telefone — padrão único da frota

## Por quê

A Meta entrega o `wa_id` de celulares antigos SEM o 9º dígito (`553591107807`); a planilha, o
formulário e o portal trazem COM o 9 (`5535991107807`), com ou sem `55`, com máscara, com `+`.
Comparar o cru separou a resposta da campanha do contato que recebeu o template: contato novo,
conversa nova, IA sem o contexto (kailos prod 2026-10-29, "Alves imports", 6 pares duplicados).
Cada app tinha o seu normalizador (`_normalize_br_phone` ×4, `normalize_wa_phone`,
`normalize_phone_br`, sufixo de 8 dígitos…) e cada tela exibia de um jeito.

## A regra

- **Canônico = só dígitos com DDI, sem `+`** (E.164 sem o sinal). Brasil: `55` + DDD + número.
  - Celular SEMPRE com o 9º dígito: 8 dígitos começando em 6-9 ganham o 9 (`553591107807` →
    `5535991107807`). Fixo (2-5) fica com 12 dígitos — um 9 na frente viraria OUTRA linha.
  - Sem `+`/`00`, 10-11 dígitos são DDD + número. Com `+`/`00` é internacional. `0` à esquerda é
    prefixo de longa distância e cai. DDD com `0` é inválido; 13 dígitos sem o 9 é inválido.
  - Estrangeiro fica com os dígitos como vieram (8-15). EUA sem `+` não colide com DDD+celular: o
    2º dígito do código de área nunca é 9.
  - Idempotente: a API devolve o canônico e recebe ele de volta igual.
- É o valor que se **grava, compara e devolve na API**. A tela formata na exibição.
- **Envio à Meta NÃO usa o canônico quando já existe `wa_id`.** O destino é o `wa_id` que a Meta
  conhece (seção "Backend — ENVIO" abaixo). O canônico só é destino quando o contato ainda não tem
  `wa_id` (1º template para um lead). Isso funciona em prod: o template "Alves" foi entregue e lido
  em 2026-10-29.

## Arquivos canônicos — CÓPIA IDÊNTICA em todo app (nunca reescreva, copie do kailos)

| Arquivo | O quê |
| --- | --- |
| `backend/src/api/core/phones.py` | `canonical_phone`, `phone_lookup_variants`, `is_br_mobile`, `PhoneNumber`/`OptionalPhoneNumber` (Pydantic) |
| `backend/tests/core/test_phones.py` | casos de regressão (mesmos do front) |
| `frontend/src/lib/utils/phone.ts` | `canonicalPhone`, `formatPhone`, `localPhoneDigits`, `phoneFieldError`, `whatsAppUrl`, `telUrl` |
| `frontend/src/lib/utils/phone.test.ts` | espelho dos casos |
| `frontend/src/components/ui/phone-input.tsx` | `PhoneInput` sobre o `MaskedInput` (só em app que tem `MaskedInput`) |

Mudou a regra? Muda Python + TS + o SQL abaixo no MESMO commit, e propaga para a frota inteira.
Processo Python separado com `pyproject` próprio (ex.: `cron/` do promoservice) que não importa
`api.*` leva uma cópia idêntica de `phones.py` no próprio pacote.

## Backend — toda ENTRADA canonicaliza

- **Formulário/API**: campo de telefone no schema de entrada = `PhoneNumber` (obrigatório) ou
  `OptionalPhoneNumber`. Aceita qualquer grafia, guarda o canônico, recusa lixo com
  "Telefone inválido: informe DDD + número…". Nunca `str` cru + `re.sub(r"\D", …)` no service.
- **Webhook da Meta** (mensagem, status, ligação): contato = `canonical_phone("+" + wa_id) or wa_id`.
  O `wa_id` é sempre internacional — o `+` impede que um `wa_id` de 10-11 dígitos de outro país
  vire DDD brasileiro.
- **Planilha/importação/lead de portal/integração**: `canonical_phone(raw)`; `None` = sem telefone
  (linha pulada/sinalizada, nunca gravada crua).
- **Ids da plataforma NÃO são telefone de pessoa.** Ficam crus, porque são o endereço que a Meta
  reconhece:
  - `phone_number_id` e `display_phone_number` do número da loja;
  - a chave de conversa da Meta que o app guarda como veio (`wa_conversation_phone`);
  - o `whatsapp_wa_id` do contato (seção "Backend — ENVIO").
- **Proibido** normalizador local (`_normalize_br_phone`, `normalize_wa_phone`,
  `normalize_lead_phone`, sufixo de 8 dígitos `RIGHT(phone, 8)`): apague e chame `core/phones.py`.

## Backend — BUSCA por telefone tolera o legado

Linha gravada antes do padrão pode estar sem o 9 ou sem o 55. Toda busca por telefone:

```python
variants = phone_lookup_variants(raw)  # canônico primeiro
row = await conn.fetchrow(
    """SELECT * FROM contacts
       WHERE organization_id = $1 AND phone = ANY($2::text[])
       ORDER BY array_position($2::text[], phone::text) NULLS LAST, id
       LIMIT 1""",
    org_id, variants,
)
```

O `ORDER BY` prefere a grafia canônica e, empatado, a linha mais antiga (uuidv7) — a que recebeu o
template. Teste de regressão por app: inbound com o `wa_id` SEM o 9 cai no MESMO contato/conversa do
envio COM o 9 (kailos `tests/whatsapp/test_template_button_reply.py`).

## Backend — ENVIO vai para o `wa_id` que a Meta conhece

**Por quê.** Incidente no emporion em 2026-11-07, piloto NV Grill no número de TESTE da Meta:
- A mensagem do Maurício chegou com `from` = `556499512546`, sem o 9.
- O contato foi gravado com o canônico `5564999512546`, e a IA respondeu para ele.
- A Meta recusou com `(#131030) Recipient phone number not in allowed list`: a lista de teste compara o número EXATO.
- O consumer tentou 3 vezes; a cada tentativa o LLM rodou de novo e o envio falhou.

O endereço que a Meta reconhece é o `wa_id`, não o canônico. Responder para ele vale no número de teste e no de produção.

**A regra:**
- **Identidade:** continua o canônico (`contacts.phone`), com busca, deduplicação e exibição como acima.
- **Destino:** é a coluna `contacts.whatsapp_wa_id`, `VARCHAR(32)` NULL, sem índice (nunca é buscada).
  - O webhook grava ali o `from` cru de TODA mensagem recebida, com `UPDATE … WHERE whatsapp_wa_id IS DISTINCT FROM $2`.
  - Todo envio grava ali o `contacts[0].wa_id` que a Meta devolve, quando vier e for diferente. É assim que o 1º template para um lead aprende o `wa_id`.
- **Função única de destino** no serviço do WhatsApp: `whatsapp_recipient(contact) -> contact["whatsapp_wa_id"] or contact["phone"]`.
  - Passam por ela TODOS os caminhos: texto livre, mídia, link, interativo, reação, template, campanha, aviso/follow-up e ligação (iniciar e pedir permissão).
  - Nada de `contact["phone"]` como `to` fora dela.
  - Ela NÃO mora em `core/phones.py`, que é cópia idêntica da frota e não conhece WhatsApp.
- **Mensagem enviada:** a linha guarda em `wa_conversation_phone` o destino realmente usado.
- **Backfill na mesma migration:** o último `from` de entrada de cada contato.
  ```sql
  UPDATE contacts c SET whatsapp_wa_id = m.wa_conversation_phone
  FROM (SELECT DISTINCT ON (contact_id) contact_id, wa_conversation_phone
        FROM whatsapp_messages
        WHERE direction = 'inbound' AND contact_id IS NOT NULL AND wa_conversation_phone <> ''
        ORDER BY contact_id, created_at DESC, id DESC) m
  WHERE m.contact_id = c.id;
  ```
- **Testes de regressão, por app:**
  - Entrada com `wa_id` SEM o 9: o contato fica com `phone` canônico COM o 9 e `whatsapp_wa_id` cru, e a resposta sai com `to` = o `wa_id` cru. Capture o argumento do client.
  - Contato sem `wa_id`: o envio vai ao canônico, e o `wa_id` devolvido pela Meta é gravado.

## Front — exibir, digitar, validar, linkar

- **Exibir**: `formatPhone(valor)` em TODA tela (lista, card, detalhe, picker, impressão, vitrine):
  "(35) 99110-7807", fixo "(34) 3210-1234", estrangeiro "+14155552671". Nunca o valor cru, nunca
  um `formatPhone` local (o antigo de `masks.ts` saiu: quebrava com o `55` na frente).
- **Digitar**: `PhoneInput` (`value` aceita o canônico que a API devolve; `onChange` emite os
  dígitos LOCAIS; o backend canonicaliza). Não canonicaliza por tecla — "(35) 9911-0780" é celular
  pela metade. Colar "+55 35 99110-7807" funciona. O `MaskedInput mask="phone"` direto num form
  vira `PhoneInput`.
- **Validar**: `phoneFieldError(valor)` no validator do campo (TanStack Form/Zod
  `.refine((v) => !phoneFieldError(v), …)` ou `superRefine` com a mensagem). Mais estrito que o
  backend: 10 dígitos começando em 6-9 = "Celular tem 9 dígitos depois do DDD."
- **Linkar**: `whatsAppUrl(valor)` (`https://wa.me/<canônico>`) e `telUrl(valor)` (`tel:+<canônico>`).
  Nunca montar `wa.me`/`tel:` na mão.

## Dado legado — migration de normalização (uma por app)

Converte as colunas de telefone de PESSOA para o canônico com uma função SQL que espelha
`canonical_phone` (conferida contra o Python em 20.027 casos, 0 divergências, 2026-10-29). `pg_temp`
some com a sessão; dbmate roda o `up` numa transação só, então a função vale para a migration toda.

```sql
-- migrate:up
CREATE OR REPLACE FUNCTION pg_temp.canonical_br(d text) RETURNS text
LANGUAGE sql IMMUTABLE AS $fn$
  SELECT CASE
    WHEN substr(d, 3, 2) LIKE '%0%' THEN NULL
    WHEN length(d) = 13 THEN CASE WHEN substr(d, 5, 1) = '9' THEN d END
    WHEN substr(d, 5, 1) IN ('6', '7', '8', '9') THEN substr(d, 1, 4) || '9' || substr(d, 5)
    WHEN substr(d, 5, 1) IN ('2', '3', '4', '5') THEN d
  END
$fn$;

CREATE OR REPLACE FUNCTION pg_temp.canonical_phone(raw text) RETURNS text
LANGUAGE plpgsql IMMUTABLE AS $fn$
DECLARE
  txt text := btrim(coalesce(raw, ''));
  intl boolean := left(txt, 1) = '+' OR left(txt, 2) = '00';
  d text := regexp_replace(txt, '\D', '', 'g');
  national text;
BEGIN
  d := CASE WHEN left(txt, 2) = '00' THEN substr(d, 3) ELSE ltrim(d, '0') END;
  IF NOT intl AND length(d) IN (10, 11) THEN
    national := pg_temp.canonical_br('55' || d);
    IF national IS NOT NULL THEN
      RETURN national;
    END IF;
  END IF;
  IF left(d, 2) = '55' THEN
    RETURN CASE WHEN length(d) IN (12, 13) THEN pg_temp.canonical_br(d) END;
  END IF;
  RETURN CASE WHEN length(d) BETWEEN 8 AND 15 THEN d END;
END
$fn$;

-- (a) Tabela em que o telefone É a identidade buscada (contatos do WhatsApp, `users.phone` unique):
--     nunca cria duplicata. <escopo> = colunas do UNIQUE que contém o telefone; sem UNIQUE, o tenant.
WITH normalized AS (
  SELECT id, pg_temp.canonical_phone(phone) AS canonical,
         count(*) OVER (PARTITION BY organization_id, pg_temp.canonical_phone(phone)) AS same_number
  FROM contacts
  WHERE phone IS NOT NULL
)
UPDATE contacts t SET phone = n.canonical
FROM normalized n
WHERE t.id = n.id AND n.canonical IS NOT NULL AND n.canonical <> t.phone AND n.same_number = 1;

-- (b) Tabela que só REFERENCIA o número (lead, negociação, financiamento, destinatário, lembrete,
--     cliente/fornecedor identificado por documento): a mesma pessoa repete, toda linha muda.
UPDATE portal_leads SET phone = pg_temp.canonical_phone(phone)
WHERE pg_temp.canonical_phone(phone) IS NOT NULL AND pg_temp.canonical_phone(phone) <> phone;

DROP FUNCTION pg_temp.canonical_phone(text);
DROP FUNCTION pg_temp.canonical_br(text);

-- migrate:down
-- Sem volta: a grafia antiga é o MESMO número; a busca por variantes acha as duas.
```

- **Identidade nunca ganha duplicata** (forma (a), `same_number = 1`): duas linhas que viram o mesmo
  número são a mesma pessoa gravada duas vezes. Ficam como estão (a busca acha as duas, prefere a
  mais antiga); juntar é escrita em prod que só sai com OK do usuário. Usar (a) numa tabela de
  referência pularia toda pessoa que aparece 2× (o lead que mandou 3 propostas) — por isso (b).
- Lixo (`canonical_phone` = NULL) fica como está.
- Não toque ids da plataforma (ver acima) nem telefone dentro de JSONB de payload.
- Telefone em JSONB de configuração (`settings.branding.phone`) não migra: o model usa
  `OptionalPhoneNumber`, que canonicaliza na LEITURA e recusa lixo — antes de trocar o tipo, confira
  em prod que nenhum valor gravado é inválido (senão a leitura da config quebra).
- Antes de commitar: conte no banco local quantas linhas cada UPDATE mexe e quantas o
  `same_number > 1` pulou; o deploy roda `pg-backup now` antes da migration.

## Regra de negócio por app (fica em cima, não substitui)

O canônico é universal; o app pode exigir MAIS num campo específico — ex.: nexarena só aceita
celular brasileiro como identidade (`is_br_mobile(canonical_phone(x))`, unique em `users.phone`).
Essa checagem vive no service/schema do app, chamando `core/phones.py`.
