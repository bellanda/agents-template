/**
 * Prompt opened ready-made on chatgpt.com by the "Montar com o ChatGPT" button.
 *
 * ChatGPT interviews the business owner and returns the Markdown they paste into the instructions
 * screen; that text is appended at runtime to the agent's base system prompt as tenant
 * instructions. Canonical builder (decision 2026-10-01, frontend standardization): the STRUCTURE
 * below is the kailos prompt, made domain-agnostic. Apps never fork this file — they pass a
 * `ChatGptBuilderContext` with their own domain text:
 *
 *   buildChatGptBuilderPrompt({
 *     platformName: "Kailos",
 *     businessName: org.name,
 *     businessDescription: "loja de veículos",
 *     knownFacts: [{ label: "Cidade", value: org.city }],
 *     platformHandles: ["os dados dos veículos em estoque", "equipes e gatilhos de transferência"],
 *     domainTopics: ["O que vende: seminovos, 0 km, motos...", "Pagamento: financiamento, entrada..."],
 *     domainSections: ["O que vendemos", "Pagamento e troca"],
 *     deliveryTitle: "CONFIGURAÇÃO DA LOJA",
 *   });
 *
 * Fixed skeleton (same in every app): context -> "the platform ALREADY handles this" -> interview
 * (tone, greeting, <domain topics>, FAQ, never-say) -> ONE Markdown block with fixed headings.
 *
 * Why the "already handled" list exists: whatever the runtime injects on its own (base rules, the
 * "I am a virtual assistant" identity rule, date/time, business hours, teams, catalog...) has its
 * own screen or code. Repeating it in the tenant Markdown creates two sources of truth that
 * diverge on the first edit of either (gate frontend, ref agent-instructions.md). Always fill
 * `platformHandles` with what YOUR runtime injects.
 *
 * Exceptions (2026-11-06, 3-layer contract: L1 platform rules in code, L2 this Markdown = store
 * FACTS and its own answers to day-to-day anomalies, L3 tools + injected context): with
 * `exceptionTopics` the interview runs in ROUNDS (round 1 = interview topics, round 2 = "how does
 * the business handle each situation") and the delivery ends with "### Situações especiais", one
 * short line per answered exception. Never behaviour/flow rules, never data the app injects.
 *
 * Delivery: the prompt always goes by clipboard + the launch dialog (`ChatGptLaunchDialog`, decision
 * 2026-11-06). A prefilled `?prompt=` URL is gone: encoded, the prompt is far past the ~4k chars
 * chatgpt.com tolerates (an accent costs 6, a space costs 3).
 */

/** Empty chat the launch dialog opens; the user pastes the clipboard prompt there. */
export const CHATGPT_URL = "https://chatgpt.com/";

const EXCEPTIONS_SECTION = "Situações especiais";

const DEFAULT_CHANNEL = "WhatsApp";
const DEFAULT_DELIVERY_TITLE = "CONFIGURAÇÃO DO ATENDIMENTO";
const DEFAULT_WRITING_RULE =
  'Escreva falando com o assistente, em segunda pessoa ("Você atende pelo..."), em frases curtas e só com o que eu confirmei.';

/** Generic domain topics/sections, used when an app has nothing more specific to ask. */
const DEFAULT_DOMAIN_TOPICS = [
  "O que o negócio oferece e o que está fora do escopo do atendimento.",
  "Políticas e regras: prazos, pagamento, cancelamento, atendimento presencial ou remoto, horários.",
] as const;
const DEFAULT_DOMAIN_SECTIONS = ["Escopo do atendimento", "Políticas e regras"] as const;

/** What every platform built on the agents template guarantees (rules, identity, clock). */
const BASE_PLATFORM_HANDLES = [
  "as regras-base de comportamento do assistente",
  "dizer que é um assistente virtual quando perguntarem",
  "a data e a hora atuais",
] as const;

export interface ChatGptKnownFact {
  /** pt-BR label shown to ChatGPT, e.g. "Cidade". */
  label: string;
  /** Empty/nullish facts are dropped, so callers can pass the raw organization fields. */
  value: string | null | undefined;
}

export interface ChatGptToolInfo {
  /** Human-readable pt-BR name of what the tool does ("Transferir para uma equipe"), NOT the function id. */
  name: string;
  description?: string;
}

export interface ChatGptBuilderContext {
  /** Product name for the opening line ("pela plataforma X"). Omitted = no platform mention. */
  platformName?: string;
  /** Channel the assistant answers on. Default "WhatsApp". Used as "atende ... por {channel}". */
  channel?: string;
  /** Business name already registered in the app; ChatGPT must not ask for it. */
  businessName?: string;
  /** What the business is, from the app's domain ("loja de veículos"). Omitted = any business. */
  businessDescription?: string;
  /** Other registered facts (city, address, phone...) — passed ready so ChatGPT never re-asks. */
  knownFacts?: ChatGptKnownFact[];
  /** What YOUR runtime already injects (hours, teams, catalog...), added to the base list. */
  platformHandles?: string[];
  /** Tools the agent really has; stops ChatGPT from promising actions the assistant can't do. */
  tools?: ChatGptToolInfo[];
  /** Domain interview topics, between "greeting" and "FAQ". Plain sentences; numbering is added. */
  domainTopics?: string[];
  /** Markdown `###` sections of the delivered text for those topics, between "Saudação" and "FAQ". */
  domainSections?: string[];
  /**
   * Top `##` heading of the delivered block. Match the name your base prompt uses for the tenant
   * section (kailos: "CONFIGURAÇÃO DA LOJA"). Default "CONFIGURAÇÃO DO ATENDIMENTO".
   */
  deliveryTitle?: string;
  /**
   * Full replacement of the interview list (tone/greeting/domain/FAQ defaults are dropped). Use when
   * the app's own prompt owns behavior and the tenant text must carry store FACTS only (kailos,
   * 2026-10-09). Plain sentences; numbering is added.
   */
  interviewTopics?: string[];
  /** Full replacement of the delivered `###` sections (same use as `interviewTopics`). */
  deliverySections?: string[];
  /**
   * Day-to-day exceptions the owner answers in round 2 ("how does the business handle each one").
   * Phrase as short questions about how THE BUSINESS handles it; facts only, never behaviour rules.
   * Adds a final "### Situações especiais" section to the delivery.
   */
  exceptionTopics?: readonly string[];
  /** Replaces the closing "write in second person" instruction with app-specific writing rules. */
  writingRules?: string[];
}

function bulletList(items: readonly string[]): string {
  return items.map((item) => `- ${item}`).join("\n");
}

function openingLine(context: ChatGptBuilderContext): string {
  const channel = context.channel?.trim() || DEFAULT_CHANNEL;
  const platform = context.platformName?.trim();
  const platformPart = platform ? `, pela plataforma ${platform}` : "";
  const description = context.businessDescription?.trim();
  const businessPart = description
    ? ` O negócio é: ${description}.`
    : " Pode ser qualquer tipo de negócio — adapte as perguntas ao que eu responder.";
  return `Você vai me ajudar a escrever as instruções do assistente de IA que atende os clientes do meu negócio por ${channel}${platformPart}.${businessPart}`;
}

function knownFactsBlock(context: ChatGptBuilderContext): string {
  const facts: ChatGptKnownFact[] = [
    { label: "Nome do negócio", value: context.businessName },
    ...(context.knownFacts ?? []),
  ];
  const lines = facts.flatMap(({ label, value }) => {
    const text = value?.trim();
    return text ? [`${label}: ${text}`] : [];
  });
  if (lines.length === 0) return "";
  return `\n\nDados que o negócio já cadastrou — use como estão e não pergunte de novo:\n${bulletList(lines)}`;
}

function toolsBlock(tools: readonly ChatGptToolInfo[] | undefined): string {
  if (!tools || tools.length === 0) return "";
  const lines = tools.map((tool) =>
    tool.description ? `${tool.name}: ${tool.description}` : tool.name
  );
  return `\n\nFerramentas que o assistente JÁ tem — não explique como funcionam e não prometa nenhuma ação além destas:\n${bulletList(lines)}`;
}

function interviewTopics(context: ChatGptBuilderContext): string[] {
  if (context.interviewTopics) return context.interviewTopics;
  return [
    "Tom de voz: nome do assistente (se tiver), mais formal ou mais próximo, se pode usar emoji, como se dirigir ao cliente.",
    "Saudação: a primeira mensagem para quem chega.",
    ...(context.domainTopics ?? DEFAULT_DOMAIN_TOPICS),
    "As perguntas que os clientes fazem todo dia, com a resposta certa.",
    "O que o assistente nunca deve dizer ou prometer.",
  ];
}

function deliverySections(context: ChatGptBuilderContext): string[] {
  if (context.deliverySections) return context.deliverySections;
  return [
    "Identidade",
    "Saudação",
    ...(context.domainSections ?? DEFAULT_DOMAIN_SECTIONS),
    "Perguntas frequentes",
    "Nunca diga",
  ];
}

/** The full prompt text typed into chatgpt.com. */
export function buildChatGptBuilderPrompt(context: ChatGptBuilderContext = {}): string {
  const handles = [...BASE_PLATFORM_HANDLES, ...(context.platformHandles ?? [])];
  const topics = interviewTopics(context).map((topic, index) => `${index + 1}. ${topic}`);
  const sections = deliverySections(context).map((section) => `### ${section}`);
  const deliveryTitle = context.deliveryTitle?.trim() || DEFAULT_DELIVERY_TITLE;
  const closing = context.writingRules
    ? `Regras de escrita:\n${bulletList(context.writingRules)}`
    : DEFAULT_WRITING_RULE;

  return `${openingLine(context)}${knownFactsBlock(context)}

A plataforma JÁ cuida disto, então não pergunte nem escreva nada a respeito:
${bulletList(handles)}${toolsBlock(context.tools)}

${interviewBlock(topics, context.exceptionTopics)}

Se eu pular algo, deixe de fora. Nunca invente dado do negócio.

No fim, entregue UM único bloco de código Markdown, pronto para copiar, com estes títulos (título sem conteúdo fica de fora):

## ${deliveryTitle}
${sections.join("\n")}${exceptionsDelivery(context.exceptionTopics)}

${closing}`;
}

function interviewBlock(
  topics: readonly string[],
  exceptions: readonly string[] | undefined
): string {
  const intro =
    "Me entreviste em português, com 3 a 5 perguntas por vez, e espere minha resposta antes de seguir.";
  if (!exceptions || exceptions.length === 0) return `${intro} Cubra:\n${topics.join("\n")}`;
  return `${intro} Em 2 rodadas.
Rodada 1:
${topics.join("\n")}

Rodada 2 — situações do dia a dia: pergunte como o negócio resolve cada uma (quem trata, por onde, o que oferece) e pule as que eu não souber:
${bulletList(exceptions)}`;
}

function exceptionsDelivery(exceptions: readonly string[] | undefined): string {
  if (!exceptions || exceptions.length === 0) return "";
  return `\n### ${EXCEPTIONS_SECTION} (uma linha curta por situação que respondi: "Situação: o que o negócio faz / quem trata / por onde"; só fatos)`;
}
