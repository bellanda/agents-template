> Reference do gate `integrations` (política de plataforma da Meta). Complementa `meta-invariants.md`
> (invariantes técnicos) e `meta-app-setup.md` (runbook de código). Aqui não tem código — tem o que a
> Meta permite, o que ela pune, e o que a submissão pode declarar.

# Meta — Política de plataforma

O código pode estar impecável e o produto ser reprovado ou o número da loja ser restringido. Estas
regras não são validadas em tempo de envio: a Meta pune depois, pelo comportamento de quem recebeu.

## As duas portas — aprovação ≠ permissão

Confundir isso é o erro mais caro do domínio.

| Porta                      | O que ela garante                                          | O que ela NÃO garante           |
| -------------------------- | ---------------------------------------------------------- | ------------------------------- |
| **Template aprovado**      | a Meta revisou o **conteúdo** (política, categoria, forma) | que o destinatário queira       |
| **Mensagem paga**          | entrega                                                    | autorização para aquele contato |
| **Opt-in do destinatário** | autorização                                                | nada sobre o conteúdo           |

Pagar não compra consentimento. Selo postal não autoriza spam.

## Janela de serviço de 24h

- Enquanto houver mensagem **recebida** do consumidor nas últimas 24h, o negócio responde **livre**:
  texto, mídia, interactive, sem template e sem tarifa por mensagem.
- Fora da janela, **só template aprovado**. A Graph API recusa free-form com erro `131047`.
- Barre isso no **serviço**, antes de chamar a Meta — não no cliente HTTP (o template justamente não
  pode ser barrado pela janela) e não na Meta (aí o custo e a violação já aconteceram).
- O carimbo da última inbound é dado quente: denormalize numa coluna da conversa e compare **no
  Postgres** (`last_inbound_at > NOW() - INTERVAL '24 hours'`), nunca com o relógio do processo.
- Envio assíncrono re-checa: a janela pode fechar entre a inbound e a resposta gerada por LLM.

## Categorias de template

| Categoria        | Quando                                                    | Exigência de opt-in            |
| ---------------- | --------------------------------------------------------- | ------------------------------ |
| `UTILITY`        | atrelado a algo que a pessoa pediu ou fez (pedido, agenda) | histórico de interação basta   |
| `MARKETING`      | promoção, reativação, novidade                            | **aceite explícito registrado** |
| `AUTHENTICATION` | código de verificação                                      | o próprio fluxo de login       |

Categoria errada é motivo de rejeição e de recategorização unilateral pela Meta. Texto promocional em
`UTILITY` reprova.

## Opt-in — o que conta e onde grava

**O opt-in não precisa acontecer no WhatsApp.** Não existe ovo-e-galinha: colete em qualquer canal e
guarde a evidência. Não vale disparar frio pedindo permissão — essa primeira mensagem já é
business-initiated e já exigiria o opt-in que ela está pedindo.

Conta como opt-in quando a pessoa (1) forneceu o número, (2) concordou de forma afirmativa e clara em
receber mensagens **daquele negócio** **no WhatsApp**, e (3) existe registro disso.

Caminhos legítimos, do mais barato ao mais caro:

- **Dentro da conversa** — a pessoa escreve primeiro, abre a janela de 24h, e você pergunta em texto
  livre. Custo zero, evidência forte (o `wamid` da resposta dela). É o que converte inbox existente em
  base de marketing.
- **`wa.me` / QR** no site, bio, vitrine, nota fiscal, balcão — a pessoa inicia.
- **Click-to-WhatsApp Ads** — o produto pago da Meta para público frio. O usuário clica e inicia; o
  custo migra de por-mensagem para por-clique e o contato entra aquecido. É a resposta certa para
  "tenho uma lista e quero alcance", que **não** é disparar para a lista.
- **Formulário / cadastro** com caixa de aceite citando WhatsApp e o nome do negócio.

Grave sempre quatro coisas: `opt_in`, `opt_in_at`, `opt_in_source` e `opt_in_evidence` (texto do
aceite, URL do formulário ou `wamid`). Sem `source` e `evidence` você não tem defesa se a Meta
contestar. Default do flag é **`false`** — assumir aceite de quem nunca foi perguntado já é a violação.

## Opt-out é obrigatório

Inbound com palavra de saída (`PARAR`, `SAIR`, `CANCELAR`, `STOP`) marca opt-out **permanente** para
marketing. Ignorar isso derruba a nota do número mais rápido que qualquer outra coisa. Opt-out nunca
some por reimportação de lista.

## Qualidade e teto do número

- **Quality rating** por número (verde/amarelo/vermelho) alimentado por bloqueio e denúncia. Vermelho
  derruba o teto e pode restringir o número.
- **Messaging limit tier**: 250 → 1K → 10K → 100K → ilimitado contatos únicos por 24h. Lista grande
  sai em rampa, não num dia.
- Produto que dispara em massa **precisa** de: ritmo respeitando o tier, leitura da nota antes e
  durante, pausa automática na queda, e kill switch manual.
- Num SaaS multi-tenant onde cada cliente tem WABA própria, o estrago começa no número do cliente —
  mas padrão repetido entre tenants sobe para **o seu Meta App / Business Manager**.

## Disclosure de IA

A Meta **não** exige anúncio proativo de que o atendimento é automatizado. Exige não enganar.

- Regra: não anuncia sem ser perguntado; se perguntarem se é robô/IA/humano, **assume**; nunca nega.
- **A regra tem que ser concatenada DEPOIS do texto configurável do tenant.** Prompt-base que declara
  a config do cliente como "verdade sobre identidade", somada a um campo de prompt livre sem
  validação, permite ao tenant instruir o agente a se passar por humano. Guardrail antes do texto do
  tenant é sugestão, não trava.
- Se a política de privacidade do produto tem cláusula de atendimento automatizado, o comportamento do
  agente precisa bater com ela.

## App Review — descrição e gravação

A descrição e o screen recording precisam ser espelho um do outro. Rejeição mais comum é descrição
genérica; a segunda é gravação que não mostra o app.

- Escreva em inglês, com atores nomeados: quem é o negócio, quem é o consumidor, **quem inicia**.
- Enumere as chamadas por endpoint, na ordem em que a gravação vai mostrá-las.
- **NUNCA declare capacidade que existe no código mas não tem call site.** Se `send_template` está
  implementado e ninguém chama, ele não entra na descrição nem na gravação.
- Grave o **seu app**, com a barra de URL visível, mais a tela do celular no mesmo quadro. Sem slides,
  sem Graph API Explorer, sem corte no meio de um passo. UI em outro idioma precisa de legenda em
  inglês.
- Mostre o ciclo inteiro, incluindo desconectar o número no fim.
- Não grave caminho de token manual nem link `wa.me` — o primeiro parece gambiarra, o segundo não é
  chamada de API.
- Forneça login de teste e o número para o revisor iniciar a conversa.
- Produto customer-initiated e produto com disparo são **submissões diferentes**. Não reaproveite o
  texto de um no outro.

## Don'ts

- **NUNCA** free-form fora da janela de 24h — fora dela, só template aprovado.
- **NUNCA** mensagem business-initiated sem opt-in registrado com origem e evidência.
- **NUNCA** disparo frio pedindo permissão — é a violação pedindo licença para si mesma.
- **NUNCA** default `true` em flag de opt-in.
- **NUNCA** marketing para quem deu opt-out, mesmo que reapareça numa lista nova.
- **NUNCA** guardrail de identidade do agente antes do texto configurável do tenant.
- **NUNCA** declarar no App Review capacidade sem call site.
- **NUNCA** campanha sem rampa, sem leitura de qualidade e sem kill switch.
