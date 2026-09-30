/**
 * Prompt opened ready-made on chatgpt.com by the "Montar com o ChatGPT" button.
 *
 * ChatGPT interviews the user and returns the Markdown they paste into the instructions screen.
 * That text is appended at runtime to the agent's base system prompt as tenant instructions, so
 * the prompt lists what the platform ALREADY injects (base behavior rules, the "I am a virtual
 * assistant" identity rule, current date/time) to keep the text from repeating or contradicting
 * it. The top heading `## CONFIGURAÇÃO DO ATENDIMENTO` is the block name used as tenant section.
 * Keep the encoded URL under ~4k characters (accents cost 6, spaces cost 3).
 *
 * Product apps: extend the "already handled" list with whatever your runtime injects
 * (business hours, teams, catalog...) — keep this file the single place that knows it.
 */

const CHATGPT_URL = "https://chatgpt.com/";

function builderPrompt(businessName: string): string {
  const nameLine = businessName ? ` O negócio se chama "${businessName}".` : "";
  return `Você vai me ajudar a escrever as instruções de um assistente de IA que atende os clientes do meu negócio.${nameLine} Pode ser qualquer tipo de negócio — adapte as perguntas ao que eu responder.

A plataforma JÁ cuida disto, então não pergunte nem escreva nada a respeito:
- as regras-base de comportamento do assistente;
- dizer que é um assistente virtual quando perguntarem;
- a data e a hora atuais.

Me entreviste em português, com 3 a 5 perguntas por vez, e espere minha resposta antes de seguir. Cubra:
1. Tom de voz: nome do assistente (se tiver), mais formal ou mais próximo, se pode usar emoji, como se dirigir ao cliente.
2. Saudação: a primeira mensagem para quem chega.
3. O que o negócio oferece e o que está fora do escopo do atendimento.
4. Políticas e regras: prazos, pagamento, cancelamento, atendimento presencial ou remoto, horários.
5. As perguntas que os clientes fazem todo dia, com a resposta certa.
6. O que o assistente nunca deve dizer ou prometer.

Se eu pular algo, deixe de fora. Nunca invente dado do negócio.

No fim, entregue UM único bloco de código Markdown, pronto para copiar, com estes títulos (título sem conteúdo fica de fora):

## CONFIGURAÇÃO DO ATENDIMENTO
### Identidade
### Saudação
### Escopo do atendimento
### Políticas e regras
### Perguntas frequentes
### Nunca diga

Escreva falando com o assistente, em segunda pessoa ("Você atende pelo..."), em frases curtas e só com o que eu confirmei.`;
}

/** chatgpt.com link with the prompt already typed for this business (empty name is fine). */
export function buildChatGptBuilderUrl(businessName: string): string {
  return `${CHATGPT_URL}?prompt=${encodeURIComponent(builderPrompt(businessName.trim()))}`;
}
