# Hosts externos (CSP) e falha de rede

## CSP — todo host externo novo é uma linha no nginx, no MESMO commit

O CSP mora em `config/nginx/snippets/security-headers-base.conf` e é a única fonte de verdade (sem meta
tag no `index.html`). Quem adiciona um `fetch` para API de terceiro, um `<script src>` de SDK, um
`<iframe>` de viewer ou um `<audio>`/`<video>` **tem que liberar o host na diretiva certa** — senão o
recurso morre em produção e **o único sinal é o console do usuário**: a tela não quebra, o form só não
salva. É assim que o CEP do BrasilAPI ficou bloqueado em 4 dos 6 repos ao mesmo tempo.

| Uso no front                  | Diretiva      |
| ----------------------------- | ------------- |
| `fetch` / XHR / WebSocket     | `connect-src` |
| `<script src>`                | `script-src`  |
| `<iframe src>`                | `frame-src`   |
| `<audio>` / `<video>`         | `media-src`   |
| `<img>`                       | `img-src`     |

- **Um SDK de terceiro quase sempre precisa de DUAS diretivas** (o script, e o `fetch` que ele dispara
  sozinho ao carregar) e às vezes de três (Facebook Login, MercadoPago Bricks e qualquer widget que
  renderize iframe).
- **Diretiva declarada NÃO herda de `default-src`**: escrever `frame-src https://x.com` sem `'self'`
  bloqueia o iframe da própria origem — é a causa do "preview de PDF abre vazio".
- `media-src` ausente é pior porque é silencioso por omissão: cai no `default-src 'self'` e nem `blob:`
  passa, então o áudio que o `getBlob` resolveu não toca.
- Trate `img-src`/`media-src` como par — o upload que vira `<img>` hoje vira `<video>` amanhã pelo mesmo
  caminho (`blob:` no autenticado, `cdn.<domínio>` no público).
- **`blob:` e `data:` em `connect-src` não são "host externo" — e mesmo assim precisam estar lá.** Quem
  faz `fetch` de uma URL que a própria página criou (`URL.createObjectURL`, ou uma data URL montada no
  submit) esbarra em `connect-src` igual a um domínio de terceiro; ter `blob:` em `img-src` não cobre o
  `fetch`. É o caminho do anexo do chat: `prompt-input.convertBlobUrlToDataUrl` faz `fetch(blob:)`, e
  quem remonta o `File` para subir faz `fetch(data:)`. Sintoma: o preview da imagem aparece (isso é
  `img-src`) e o envio morre — só em produção, porque em dev o Vite não emite CSP nenhum. Regra: o
  esquema que aparece dentro de um `fetch` entra em `connect-src`, não só o host.

Auditoria: `rg 'fetch\("https://|src=\{?"https://' frontend/src` (e `rg 'createObjectURL' frontend/src`
para achar o `fetch` de `blob:`) versus o header servido de verdade
(`curl -sI https://<domínio> | rg -i content-security-policy`) — o arquivo no repo pode estar certo e o
edge servindo a versão antiga.

## `fetch` cru SÓ para API externa

BrasilAPI, IBGE, ViaCEP. Todo endpoint próprio passa pelo `ApiClient` — inclusive download (`getBlob`) e
resposta que precisa do payload sem rename (`getRaw`). Fora do client não existe interceptor de 401: a
chamada morre com o access expirado e o usuário só recupera com F5.

## Falha de rede tem UMA mensagem, em pt-BR

`lib/api/network-error.ts` (`NETWORK_ERROR_MESSAGE` + `isNetworkError`), aplicada nos **dois** pontos de
normalização: `adapters/*.transformError` E `ApiClient.defaultErrorTransform`. Corrigir só um deixa o
outro reaparecer no primeiro erro que não passa pelo adapter.

Detecção é **`error instanceof TypeError`**, NUNCA `error.message === "Failed to fetch"`: o texto muda
por browser ("Load failed" no WebKit/iOS, "NetworkError when attempting to fetch resource" no Firefox),
então casar por string manda justo o iPhone pro ramo genérico — o usuário lê "Load failed" em inglês e o
erro nem chega como `NETWORK_ERROR`. A mensagem crua do browser vai só em `details.originalError`, nunca
na tela.
