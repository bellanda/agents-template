/**
 * Prompt opened ready-made on chatgpt.com by the "Montar com o ChatGPT" button.
 *
 * ChatGPT interviews the business owner and returns the Markdown they paste into the instructions
 * screen; that text is appended at runtime to the agent's base system prompt as tenant
 * instructions. Canonical builder (decision 2026-10-01, frontend standardization): the STRUCTURE
 * below is the kailos prompt, made domain-agnostic. Apps never fork this file — they pass a
 * `ChatGptBuilderContext` with their own domain text:
 *
 *   buildChatGptBuilderUrl({
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
 * URL budget: keep the encoded URL under ~4k characters (an accent costs 6, a space costs 3) —
 * past that chatgpt.com may drop the prompt and open an empty chat. Measured: the default context
 * encodes to ~2.2k and a full kailos-like one (4 facts, 4 handles, 1 tool, 4 domain topics) to ~3.5k,
 * so long `domainTopics`/`knownFacts`/`tools` lists eat into a small margin.
 */

const CHATGPT_URL = "https://chatgpt.com/";

const DEFAULT_CHANNEL = "WhatsApp";
const DEFAULT_DELIVERY_TITLE = "CONFIGURAÇÃO DO ATENDIMENTO";

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
  return [
    "Tom de voz: nome do assistente (se tiver), mais formal ou mais próximo, se pode usar emoji, como se dirigir ao cliente.",
    "Saudação: a primeira mensagem para quem chega.",
    ...(context.domainTopics ?? DEFAULT_DOMAIN_TOPICS),
    "As perguntas que os clientes fazem todo dia, com a resposta certa.",
    "O que o assistente nunca deve dizer ou prometer.",
  ];
}

function deliverySections(context: ChatGptBuilderContext): string[] {
  return [
    "Identidade",
    "Saudação",
    ...(context.domainSections ?? DEFAULT_DOMAIN_SECTIONS),
    "Perguntas frequentes",
    "Nunca diga",
  ];
}

/** The full prompt text typed into chatgpt.com. */
function buildChatGptBuilderPrompt(context: ChatGptBuilderContext = {}): string {
  const handles = [...BASE_PLATFORM_HANDLES, ...(context.platformHandles ?? [])];
  const topics = interviewTopics(context).map((topic, index) => `${index + 1}. ${topic}`);
  const sections = deliverySections(context).map((section) => `### ${section}`);
  const deliveryTitle = context.deliveryTitle?.trim() || DEFAULT_DELIVERY_TITLE;

  return `${openingLine(context)}${knownFactsBlock(context)}

A plataforma JÁ cuida disto, então não pergunte nem escreva nada a respeito:
${bulletList(handles)}${toolsBlock(context.tools)}

Me entreviste em português, com 3 a 5 perguntas por vez, e espere minha resposta antes de seguir. Cubra:
${topics.join("\n")}

Se eu pular algo, deixe de fora. Nunca invente dado do negócio.

No fim, entregue UM único bloco de código Markdown, pronto para copiar, com estes títulos (título sem conteúdo fica de fora):

## ${deliveryTitle}
${sections.join("\n")}

Escreva falando com o assistente, em segunda pessoa ("Você atende pelo..."), em frases curtas e só com o que eu confirmei.`;
}

/** chatgpt.com link with the prompt already typed for this business (empty context is fine). */
export function buildChatGptBuilderUrl(context: ChatGptBuilderContext = {}): string {
  return `${CHATGPT_URL}?prompt=${encodeURIComponent(buildChatGptBuilderPrompt(context))}`;
}
