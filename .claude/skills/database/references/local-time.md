# Datas e fuso — o DIA é da loja, o instante é UTC

> Padrão da frota (decisão do usuário 2026-11-06: "trabalhar com datas é padrão de tudo em
> codificação"). Vale para backend, testes e frontend. Arquivos canônicos em `local-time/`
> (backend) e `skills/frontend/references/local-time/` (frontend), copiados SEM edição para cada app.

## Por que existe (incidente 2026-11-05, emporion)

Desde 2026-10 a regra estava escrita no `backend.md` e não impediu nada:

- `/orders/stats` e o relatório diário usavam `created_at::date`, que é o dia em UTC. Os pedidos do
  pico do jantar (21h–24h SP) caíam no dia seguinte.
- 6 testes falhavam só à noite. O `check.sh` roda de dia, então ninguém via.
- O emporion também não tinha recebido o port do "23:59 = fim do dia" que o kailos fez em
  2026-11-04: a loja "24h" ficava fechada 1 minuto toda noite.

Uma varredura achou o mesmo padrão em nexarena, promoservice e até no kailos (Insights, Torcida).
Regra escrita sem trava depende de o agente lembrar.

## O modelo

| Pergunta | Fuso | Como |
| --- | --- | --- |
| Quando aconteceu (instante) | UTC | `TIMESTAMPTZ`, `datetime.now(dt.UTC)`, ISO com `Z` na API |
| Que DIA/MÊS/HORA/DIA DA SEMANA é | da loja (`America/Sao_Paulo`) | `api/core/timezone.py` |

`api/core/timezone.py` (canônico: `local-time/timezone.py`) traz:

- `LOCAL_TZ` e `store_tz(org)`: a costura única para loja em outro fuso;
- `local_today(now)`: o "hoje" da loja;
- `local_day_bounds_utc(day)`: o `[início, fim)` do dia local em UTC;
- `local_date_sql(col)`: monta `(col AT TIME ZONE 'America/Sao_Paulo')::date`.

### Backend (SQL e Python)

- **Janela** (o dia X, o mês corrente): calcule em Python no fuso local e mande um intervalo
  meio-aberto em UTC, `col >= $start AND col < $end`, via `local_day_bounds_utc`. Usa o índice.
- **Agrupar por dia ou mês**: converta explicitamente.
  - `(col AT TIME ZONE 'America/Sao_Paulo')::date`
  - `date_trunc('month', col AT TIME ZONE $n)`
  - `EXTRACT(hour FROM col AT TIME ZONE $n)`
- **PROIBIDO**:
  - `col::date`, `CURRENT_DATE`, `date_trunc`/`EXTRACT`/`to_char` em instante sem `AT TIME ZONE`;
  - `$1::date` comparado direto com `TIMESTAMPTZ` (vira meia-noite do fuso da SESSÃO);
  - `date.today()`, `datetime.now()` sem fuso, `datetime.now(UTC).date()`/`.hour`/`.weekday()`;
  - parâmetro de rota `x: datetime = Query(...)`. O filtro de período manda `from=2026-11-05` (só a
    data), o Pydantic cria meia-noite SEM fuso e o asyncpg a lê no fuso do PROCESSO (UTC no
    container). No nexarena (2026-11-06), o período personalizado do Financeiro perdia o último dia
    inteiro e ganhava 21h–24h SP da véspera. A regra:
    - dia de calendário: `dt.date` → janela por `local_day_bounds_utc`, com `to` = início do dia
      seguinte e `col < $fim`;
    - instante de verdade (ISO com offset): `pydantic.AwareDatetime`, para que valor sem fuso dê
      422 em vez de deslocar em silêncio.
- **Coluna `DATE`** (vencimento, competência, `period_month`) já é dia de calendário e não precisa
  de conversão. Convenção que a trava usa: instante = `*_at`, data = `*_date`/`month`/`day`.
- **"23:59" de fechamento = fim do dia** (próxima meia-noite) em horário comercial. Senão a loja
  24h fecha 1 minuto por noite (kailos `LAST_MINUTE_OF_DAY`, 2026-11-04).
  - O instante de fechamento é a PRÓXIMA meia-noite (`slot_close_at`), nunca `combine(dia,
    time.max)`. Com 23:59:59.999999, cada virada de dia perde 1 µs, e o prazo da espera do cliente
    errava por 1 µs entre 00h e 03h SP (kailos 2026-11-06).
  - Teste de soma de expediente atravessando a meia-noite compara com `==` exato, nunca com
    `approx`, que esconde o µs.
- **Chave técnica em UTC** pode ficar (teto diário de API externa que vira em UTC, nome de pasta
  de trabalho `strftime`). Marque com `# tz-ok: <porquê>`.

### Testes — trava estática + canário de fuso

1. **Trava estática** `backend/tests/test_timezone_guard.py` (canônico `local-time/test_timezone_guard.py`).
   - Varre string SQL e chamada Python em `src/`, `pipelines/`, `cron/`, `scripts/`, `agents/`,
     `tests/` e `db/migrations/*.sql`.
   - Reprova operação de calendário em instante sem `AT TIME ZONE`, e `datetime` sem fuso em
     `Query(...)` de rota.
   - Linha correta leva `tz-ok: <porquê>` (`# tz-ok:` em Python, `-- tz-ok:` dentro do SQL).
2. **Canário de fuso**: a suíte roda com o processo pytest e o Postgres de teste em
   `Pacific/Kiritimati` (UTC+14). Lá a data local difere da de São Paulo das 07h às 24h. O bug
   que a trava não reconhece passa a falhar em horário de trabalho, não só à noite.
   - `backend/tests/conftest.py`, no topo e ANTES de qualquer import da app:
     ```python
     TEST_TIMEZONE = "Pacific/Kiritimati"
     os.environ["TZ"] = TEST_TIMEZONE
     time.tzset()
     ```
   - `backend/tests/compose.yml`, no `command:` do Postgres: `- -c` / `- timezone=Pacific/Kiritimati`.
   - `test_suite_runs_in_the_calendar_canary_zone` (dentro da trava) confere `SHOW timezone` e o
     offset do processo. Container de teste reaproveitado com config velha falha aqui, então use
     `compose up -d --wait` sempre (é idempotente).
3. **Par relógio/dado** (`rules/tests.md`):
   - o dia semeado sai do MESMO fuso em que a query compara: `local_today(now)`, nunca `CURRENT_DATE`/`date.today()`;
   - regressão de dia usa data fixa no par: pedido às 22:30 SP = 01:30Z do dia seguinte, conta no dia SP.

### Frontend

- Dia de calendário no browser = dia LOCAL do usuário, via `lib/utils/dates.ts`. Canônico:
  `skills/frontend/references/local-time/dates-local-day.ts`.
  - `toLocalDateKey(date)` gera o `YYYY-MM-DD` do `<input type="date">`, do `max` e do período;
  - `parseLocalDateKey(key)` faz o caminho inverso;
  - `addDaysToDateKey(key, n)` soma dias;
  - `utcToDateTimeLocal`/`dateTimeLocalToUtc` cuidam do `datetime-local`.
- PROIBIDO:
  - `toISOString().slice(0, 10)`/`.split("T")[0]` como "hoje" (é o dia UTC);
  - `new Date("YYYY-MM-DD")` (meia-noite UTC = dia anterior em SP);
  - `getTimezoneOffset()`/`getUTC*()` fora de `dates.ts`.
- Trava: `src/test/__tests__/timezone-guard.test.ts` (canônico
  `skills/frontend/references/local-time/timezone-guard.test.ts`).
- Exibir instante continua `formatDateTime`/`formatDate` (`Intl.DateTimeFormat`).
- A trava TS roda com `// @vitest-environment node`. O `src/test/setup.ts` global precisa
  funcionar fora do jsdom: proteja stubs de `window`/`Element` com `typeof X !== "undefined"`.
  Sem isso, a trava quebra com `Element is not defined` (akmeo e emporion, 2026-11-06).
