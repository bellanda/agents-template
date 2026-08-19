// Canonical cross-project verb standard (skill frontend, ref permissions-display.md):
// verb = last `:` segment of the permission key → fixed order, color and icon.
import {
  BadgeCheck,
  Ban,
  Banknote,
  Eye,
  FileOutput,
  HandCoins,
  KeyRound,
  Pencil,
  Play,
  Plus,
  Search,
  Send,
  Settings2,
  TicketCheck,
  Trash2,
  type LucideIcon,
} from "lucide-react";

export interface VerbMeta {
  order: number;
  label: string;
  icon: LucideIcon;
  badgeClass: string;
}

const SKY =
  "border-sky-200 bg-sky-50 text-sky-700 dark:border-sky-900 dark:bg-sky-950/40 dark:text-sky-300";
const CYAN =
  "border-cyan-200 bg-cyan-50 text-cyan-700 dark:border-cyan-900 dark:bg-cyan-950/40 dark:text-cyan-300";
const EMERALD =
  "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-300";
const AMBER =
  "border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-300";
const ROSE =
  "border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-900 dark:bg-rose-950/40 dark:text-rose-300";
const VIOLET =
  "border-violet-200 bg-violet-50 text-violet-700 dark:border-violet-900 dark:bg-violet-950/40 dark:text-violet-300";
const TEAL =
  "border-teal-200 bg-teal-50 text-teal-700 dark:border-teal-900 dark:bg-teal-950/40 dark:text-teal-300";
const INDIGO =
  "border-indigo-200 bg-indigo-50 text-indigo-700 dark:border-indigo-900 dark:bg-indigo-950/40 dark:text-indigo-300";
const LIME =
  "border-lime-200 bg-lime-50 text-lime-700 dark:border-lime-900 dark:bg-lime-950/40 dark:text-lime-300";
const ORANGE =
  "border-orange-200 bg-orange-50 text-orange-700 dark:border-orange-900 dark:bg-orange-950/40 dark:text-orange-300";
const BLUE =
  "border-blue-200 bg-blue-50 text-blue-700 dark:border-blue-900 dark:bg-blue-950/40 dark:text-blue-300";
const FUCHSIA =
  "border-fuchsia-200 bg-fuchsia-50 text-fuchsia-700 dark:border-fuchsia-900 dark:bg-fuchsia-950/40 dark:text-fuchsia-300";
const SLATE =
  "border-slate-200 bg-slate-50 text-slate-700 dark:border-slate-800 dark:bg-slate-900/40 dark:text-slate-300";

// União dos verbos de TODOS os projetos que copiam este arquivo — não é subconjunto por projeto.
// Verbo do catálogo Pydantic que falta aqui cai no fallback e imprime o verbo cru em inglês no
// badge (violação de pt-BR). Cor repetida dentro da mesma família é proposital; `order` não repete.
export const VERB_META: Record<string, VerbMeta> = {
  read: { order: 10, label: "Ver", icon: Eye, badgeClass: SKY },
  view: { order: 10, label: "Ver", icon: Eye, badgeClass: SKY },
  read_all: { order: 11, label: "Ver todas", icon: Eye, badgeClass: SKY },
  query: { order: 15, label: "Consultar", icon: Search, badgeClass: CYAN },
  create: { order: 20, label: "Criar", icon: Plus, badgeClass: EMERALD },
  generate: { order: 25, label: "Gerar", icon: FileOutput, badgeClass: EMERALD },
  update: { order: 30, label: "Editar", icon: Pencil, badgeClass: AMBER },
  settle: { order: 35, label: "Dar baixa", icon: HandCoins, badgeClass: LIME },
  delete: { order: 40, label: "Excluir", icon: Trash2, badgeClass: ROSE },
  cancel: { order: 45, label: "Cancelar", icon: Ban, badgeClass: ORANGE },
  manage: { order: 50, label: "Gerenciar", icon: Settings2, badgeClass: VIOLET },
  settings: { order: 50, label: "Configurar", icon: Settings2, badgeClass: VIOLET },
  send: { order: 55, label: "Enviar", icon: Send, badgeClass: BLUE },
  withdraw: { order: 56, label: "Sacar", icon: Banknote, badgeClass: FUCHSIA },
  approve: { order: 60, label: "Aprovar", icon: BadgeCheck, badgeClass: TEAL },
  approve_edit: { order: 61, label: "Aprovar edição", icon: BadgeCheck, badgeClass: TEAL },
  execute: { order: 65, label: "Executar", icon: Play, badgeClass: INDIGO },
  checkin: { order: 66, label: "Check-in", icon: TicketCheck, badgeClass: INDIGO },
};

const FALLBACK_VERB: VerbMeta = { order: 99, label: "", icon: KeyRound, badgeClass: SLATE };

export function verbOf(permission: string): string {
  return permission.split(":").at(-1) ?? permission;
}

export function verbMeta(permission: string): VerbMeta {
  const verb = verbOf(permission);
  return VERB_META[verb] ?? { ...FALLBACK_VERB, label: verb };
}
