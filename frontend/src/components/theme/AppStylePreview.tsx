import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { findAppStyle, type AppStyleId } from "@/lib/appearance/app-styles";
import { cn } from "@/lib/utils";
import {
  ChatCircleIcon,
  GearIcon,
  HouseIcon,
  PlusIcon,
  SlidersHorizontalIcon,
  TrendUpIcon,
  UsersIcon,
  type Icon,
} from "@phosphor-icons/react";

const PREVIEW_MENU: ReadonlyArray<{ label: string; icon: Icon; isActive?: boolean }> = [
  { label: "Início", icon: HouseIcon, isActive: true },
  { label: "Conversas", icon: ChatCircleIcon },
  { label: "Contatos", icon: UsersIcon },
  { label: "Configurações", icon: GearIcon },
];

const PREVIEW_KPIS: ReadonlyArray<{ label: string; value: string }> = [
  { label: "Conversas hoje", value: "38" },
  { label: "Novos contatos", value: "12" },
  { label: "Respondidas", value: "94%" },
];

const PREVIEW_ROWS: ReadonlyArray<{ name: string; detail: string; status: string }> = [
  { name: "Maria Souza", detail: "Quero saber o horário", status: "Aberta" },
  { name: "João Pereira", detail: "Obrigado pelo retorno", status: "Resolvida" },
];

/**
 * Um pedaço do app desenhado no estilo: sidebar, header, KPIs, botões e uma lista.
 *
 * Genérica de propósito (o template não tem domínio): um app real troca o menu, os KPIs e a
 * lista pelos DELE — nunca deixe conteúdo de outro app aqui. As cores saem do MESMO CSS do
 * estilo (`data-style-preview`, ver `styles/themes/`) e os `data-*` são os ganchos que os
 * estilos já decoram no app de verdade — a prévia é o app, não um desenho paralelo.
 */
export function AppStylePreview({ styleId }: { styleId: AppStyleId }) {
  const { mode } = findAppStyle(styleId);

  return (
    <div
      aria-hidden
      data-style-preview={styleId}
      className={cn(
        mode,
        "bg-background text-foreground border-border @container flex min-w-0 overflow-hidden rounded-xl border text-sm shadow-sm select-none"
      )}
    >
      <PreviewSidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        {/* Num celular (~300px úteis) os botões viram só ícone e nada empurra o dialog. */}
        <div
          data-app-header
          className="flex items-center justify-between gap-2 border-b px-3 py-3 @md:px-4"
        >
          <div className="min-w-0">
            <p className="leading-none font-bold tracking-tight">Início</p>
            <p className="text-muted-foreground mt-1 text-xs leading-none">Visão geral</p>
          </div>
          <div className="flex shrink-0 gap-2">
            <Button size="sm" variant="outline" tabIndex={-1}>
              <SlidersHorizontalIcon aria-hidden />
              <span className="hidden @md:inline">Filtros</span>
            </Button>
            <Button size="sm" tabIndex={-1}>
              <PlusIcon aria-hidden />
              <span className="hidden @md:inline">Novo</span>
            </Button>
          </div>
        </div>
        <div className="space-y-3 p-3 @md:p-4">
          <div className="grid grid-cols-[repeat(3,minmax(0,1fr))] gap-2">
            {PREVIEW_KPIS.map((kpi) => (
              <div
                key={kpi.label}
                data-kpi-card
                className="bg-card min-w-0 rounded-lg border p-2 @md:p-3"
              >
                <span data-kpi-icon className="text-primary">
                  <TrendUpIcon className="size-4" aria-hidden />
                </span>
                <p className="text-muted-foreground mt-2 truncate text-xs">{kpi.label}</p>
                <p className="text-sm font-bold whitespace-nowrap tabular-nums @md:text-lg">
                  {kpi.value}
                </p>
              </div>
            ))}
          </div>
          <div className="bg-card divide-y rounded-lg border">
            {PREVIEW_ROWS.map((row) => (
              <div key={row.name} className="flex items-center justify-between gap-2 p-3">
                <div className="min-w-0">
                  <p className="truncate font-medium">{row.name}</p>
                  <p className="text-muted-foreground truncate text-xs">{row.detail}</p>
                </div>
                <Badge variant="secondary" className="shrink-0">
                  {row.status}
                </Badge>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function PreviewSidebar() {
  return (
    <div
      data-sidebar="sidebar"
      className="bg-sidebar text-sidebar-foreground border-sidebar-border hidden w-44 shrink-0 flex-col gap-1 border-r p-2 sm:flex"
    >
      <p className="px-2 py-2 text-base font-bold tracking-tight">App</p>
      {PREVIEW_MENU.map(({ label, icon: Icon, isActive }) => (
        <span
          key={label}
          data-sidebar="menu-button"
          data-active={isActive ? "true" : undefined}
          className="data-[active=true]:bg-sidebar-accent data-[active=true]:text-sidebar-accent-foreground flex items-center gap-2 rounded-md px-2 py-1.5 text-xs data-[active=true]:font-medium"
        >
          <Icon className="size-4 shrink-0" aria-hidden />
          <span className="truncate">{label}</span>
        </span>
      ))}
    </div>
  );
}
