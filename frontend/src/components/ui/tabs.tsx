import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { Tabs as TabsPrimitive } from "radix-ui";

import { cn } from "@/lib/utils";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

/* ════════════════════════════════════════════════════════════════════════════
   Abas que não cabem: cheio -> compacto -> Select (nunca 2ª linha)

   Decisão do usuário (2026-10-09). A lista é `flex-nowrap` e escolhe a forma pela
   LARGURA DA PRÓPRIA `Tabs` (container query nomeado `@container/tabs`), não pela
   viewport: no notebook com a sidebar aberta a área útil cai para 700–1100px
   mesmo com viewport de 1280.

     1. cheio     — largura >= FULL do bucket: visual padrão.
     2. compacto  — entre COMPACT e FULL: gap/padding menores; o ícone FICA (usuário 2026-10-09: tirar ícone não valeu a pena).
     3. Select    — largura < COMPACT do bucket: a lista some e o Select aparece.

   Os limiares vêm de um mapa ESTÁTICO por nº exato de abas (Tailwind só
   compila literais): Select abaixo de ~5.5rem*n, compacto abaixo de ~6.6rem*n (ver TABS_TIERS).

   Causa raiz do bug anterior: `h-8` fixo na lista vencia o `h-auto` do call site,
   então o `flex-wrap` quebrava a 2ª linha POR CIMA do conteúdo e os triggers
   (`flex-1`) esticavam. Agora `min-h-8` + `flex-nowrap` + triggers `flex-none`;
   call site NÃO põe `h-auto flex-wrap`.

   `mobile="strip"` (ícone-only/1 palavra) pula as faixas: tira sempre visível.
   Abas verticais não usam container query (mantêm Select só < md).

   A troca é CSS e as DUAS formas montam sempre. NUNCA `useIsMobile()` aqui: ele
   resolve em `useEffect`, então o primeiro frame piscaria a forma errada e a
   troca de árvore remonta o painel ativo. NUNCA `overflow-x-auto` na tira.
   ════════════════════════════════════════════════════════════════════════════ */

/** A partir de 3 abas a tira não cabe em 375px. Com 2 ela cabe e o Select só atrapalha. */
const MOBILE_SELECT_MIN_TABS = 3;

type TabsTier = {
  /** Trigger do Select: escondido por padrão, aparece abaixo do limiar compacto. */
  select: string;
  /** Lista: compacta abaixo do limiar cheio e some abaixo do limiar compacto. */
  list: string;
};

/**
 * Chave = nº EXATO de abas (3..16; 17+ usa a 16). Cada linha é LITERAL de propósito: o Tailwind
 * só compila classe que aparece inteira no fonte, e `@container` não aceita `calc(var())`.
 * Largura medida em Playwright no dashboard (11 abas, ícone + rótulo, html 17px):
 * compacto (px-1) ~5.5rem/aba, cheio ~6.6rem/aba. Regra: Select abaixo de ~5.5rem*n,
 * compacto abaixo de ~6.6rem*n. Faixas largas (teto de 5/7/9/12 abas) mandavam 11 abas
 * ao Select com 61rem úteis, embora a tira compacta (~54rem) coubesse (2026-10-09).
 * `px-1!` (important) porque a variante ghost do trigger fixa `px-3` com especificidade maior.
 */
const TABS_TIERS = {
  3: {
    select: "hidden @max-[20rem]/tabs:flex",
    list: "@max-[20rem]/tabs:hidden @max-[23rem]/tabs:gap-0.5 @max-[23rem]/tabs:[&_[data-slot=tabs-trigger]]:px-1! @max-[23rem]/tabs:[&_[data-slot=tabs-trigger]]:gap-1!",
  },
  4: {
    select: "hidden @max-[23rem]/tabs:flex",
    list: "@max-[23rem]/tabs:hidden @max-[28rem]/tabs:gap-0.5 @max-[28rem]/tabs:[&_[data-slot=tabs-trigger]]:px-1! @max-[28rem]/tabs:[&_[data-slot=tabs-trigger]]:gap-1!",
  },
  5: {
    select: "hidden @max-[28rem]/tabs:flex",
    list: "@max-[28rem]/tabs:hidden @max-[34rem]/tabs:gap-0.5 @max-[34rem]/tabs:[&_[data-slot=tabs-trigger]]:px-1! @max-[34rem]/tabs:[&_[data-slot=tabs-trigger]]:gap-1!",
  },
  6: {
    select: "hidden @max-[33rem]/tabs:flex",
    list: "@max-[33rem]/tabs:hidden @max-[41rem]/tabs:gap-0.5 @max-[41rem]/tabs:[&_[data-slot=tabs-trigger]]:px-1! @max-[41rem]/tabs:[&_[data-slot=tabs-trigger]]:gap-1!",
  },
  7: {
    select: "hidden @max-[39rem]/tabs:flex",
    list: "@max-[39rem]/tabs:hidden @max-[47rem]/tabs:gap-0.5 @max-[47rem]/tabs:[&_[data-slot=tabs-trigger]]:px-1! @max-[47rem]/tabs:[&_[data-slot=tabs-trigger]]:gap-1!",
  },
  8: {
    select: "hidden @max-[44rem]/tabs:flex",
    list: "@max-[44rem]/tabs:hidden @max-[54rem]/tabs:gap-0.5 @max-[54rem]/tabs:[&_[data-slot=tabs-trigger]]:px-1! @max-[54rem]/tabs:[&_[data-slot=tabs-trigger]]:gap-1!",
  },
  9: {
    select: "hidden @max-[50rem]/tabs:flex",
    list: "@max-[50rem]/tabs:hidden @max-[60rem]/tabs:gap-0.5 @max-[60rem]/tabs:[&_[data-slot=tabs-trigger]]:px-1! @max-[60rem]/tabs:[&_[data-slot=tabs-trigger]]:gap-1!",
  },
  10: {
    select: "hidden @max-[56rem]/tabs:flex",
    list: "@max-[56rem]/tabs:hidden @max-[67rem]/tabs:gap-0.5 @max-[67rem]/tabs:[&_[data-slot=tabs-trigger]]:px-1! @max-[67rem]/tabs:[&_[data-slot=tabs-trigger]]:gap-1!",
  },
  11: {
    select: "hidden @max-[61rem]/tabs:flex",
    list: "@max-[61rem]/tabs:hidden @max-[74rem]/tabs:gap-0.5 @max-[74rem]/tabs:[&_[data-slot=tabs-trigger]]:px-1! @max-[74rem]/tabs:[&_[data-slot=tabs-trigger]]:gap-1!",
  },
  12: {
    select: "hidden @max-[67rem]/tabs:flex",
    list: "@max-[67rem]/tabs:hidden @max-[80rem]/tabs:gap-0.5 @max-[80rem]/tabs:[&_[data-slot=tabs-trigger]]:px-1! @max-[80rem]/tabs:[&_[data-slot=tabs-trigger]]:gap-1!",
  },
  13: {
    select: "hidden @max-[72rem]/tabs:flex",
    list: "@max-[72rem]/tabs:hidden @max-[87rem]/tabs:gap-0.5 @max-[87rem]/tabs:[&_[data-slot=tabs-trigger]]:px-1! @max-[87rem]/tabs:[&_[data-slot=tabs-trigger]]:gap-1!",
  },
  14: {
    select: "hidden @max-[78rem]/tabs:flex",
    list: "@max-[78rem]/tabs:hidden @max-[93rem]/tabs:gap-0.5 @max-[93rem]/tabs:[&_[data-slot=tabs-trigger]]:px-1! @max-[93rem]/tabs:[&_[data-slot=tabs-trigger]]:gap-1!",
  },
  15: {
    select: "hidden @max-[83rem]/tabs:flex",
    list: "@max-[83rem]/tabs:hidden @max-[100rem]/tabs:gap-0.5 @max-[100rem]/tabs:[&_[data-slot=tabs-trigger]]:px-1! @max-[100rem]/tabs:[&_[data-slot=tabs-trigger]]:gap-1!",
  },
  16: {
    select: "hidden @max-[89rem]/tabs:flex",
    list: "@max-[89rem]/tabs:hidden @max-[107rem]/tabs:gap-0.5 @max-[107rem]/tabs:[&_[data-slot=tabs-trigger]]:px-1! @max-[107rem]/tabs:[&_[data-slot=tabs-trigger]]:gap-1!",
  },
} as const satisfies Record<number, TabsTier>;

/**
 * Variante `iconTier` (todas as abas têm ícone): entre o Select e o compacto entra o tier "ícones" —
 * aba inativa mostra só o ícone (`text-[0px]` zera o rótulo; o texto continua no DOM, então o nome
 * acessível fica e `TabsTrigger` põe `title`), a ATIVA mantém ícone + rótulo. O Select só entra
 * abaixo de ~2.75rem*(n-1) + 7rem (inativas só-ícone + rótulo da ativa). Os limiares de
 * compacto/ícones usam o mesmo `c` do mapa acima (o antigo limiar do Select).
 */
const TABS_ICON_TIERS = {
  3: {
    select: "hidden @max-[13rem]/tabs:flex",
    list: "@max-[13rem]/tabs:hidden @max-[20rem]/tabs:[&_[data-slot=tabs-trigger]:not([data-state=active])]:px-2! @max-[20rem]/tabs:[&_[data-slot=tabs-trigger]:not([data-state=active])]:text-[0px] @max-[20rem]/tabs:[&_[data-slot=tabs-trigger]:not([data-state=active])]:[&>:not(svg)]:hidden @max-[20rem]/tabs:[&_[data-slot=tabs-trigger]:not([data-state=active])]:[&_svg]:mr-0!",
  },
  4: {
    select: "hidden @max-[16rem]/tabs:flex",
    list: "@max-[16rem]/tabs:hidden @max-[23rem]/tabs:[&_[data-slot=tabs-trigger]:not([data-state=active])]:px-2! @max-[23rem]/tabs:[&_[data-slot=tabs-trigger]:not([data-state=active])]:text-[0px] @max-[23rem]/tabs:[&_[data-slot=tabs-trigger]:not([data-state=active])]:[&>:not(svg)]:hidden @max-[23rem]/tabs:[&_[data-slot=tabs-trigger]:not([data-state=active])]:[&_svg]:mr-0!",
  },
  5: {
    select: "hidden @max-[18rem]/tabs:flex",
    list: "@max-[18rem]/tabs:hidden @max-[28rem]/tabs:[&_[data-slot=tabs-trigger]:not([data-state=active])]:px-2! @max-[28rem]/tabs:[&_[data-slot=tabs-trigger]:not([data-state=active])]:text-[0px] @max-[28rem]/tabs:[&_[data-slot=tabs-trigger]:not([data-state=active])]:[&>:not(svg)]:hidden @max-[28rem]/tabs:[&_[data-slot=tabs-trigger]:not([data-state=active])]:[&_svg]:mr-0!",
  },
  6: {
    select: "hidden @max-[21rem]/tabs:flex",
    list: "@max-[21rem]/tabs:hidden @max-[33rem]/tabs:[&_[data-slot=tabs-trigger]:not([data-state=active])]:px-2! @max-[33rem]/tabs:[&_[data-slot=tabs-trigger]:not([data-state=active])]:text-[0px] @max-[33rem]/tabs:[&_[data-slot=tabs-trigger]:not([data-state=active])]:[&>:not(svg)]:hidden @max-[33rem]/tabs:[&_[data-slot=tabs-trigger]:not([data-state=active])]:[&_svg]:mr-0!",
  },
  7: {
    select: "hidden @max-[24rem]/tabs:flex",
    list: "@max-[24rem]/tabs:hidden @max-[39rem]/tabs:[&_[data-slot=tabs-trigger]:not([data-state=active])]:px-2! @max-[39rem]/tabs:[&_[data-slot=tabs-trigger]:not([data-state=active])]:text-[0px] @max-[39rem]/tabs:[&_[data-slot=tabs-trigger]:not([data-state=active])]:[&>:not(svg)]:hidden @max-[39rem]/tabs:[&_[data-slot=tabs-trigger]:not([data-state=active])]:[&_svg]:mr-0!",
  },
  8: {
    select: "hidden @max-[27rem]/tabs:flex",
    list: "@max-[27rem]/tabs:hidden @max-[44rem]/tabs:[&_[data-slot=tabs-trigger]:not([data-state=active])]:px-2! @max-[44rem]/tabs:[&_[data-slot=tabs-trigger]:not([data-state=active])]:text-[0px] @max-[44rem]/tabs:[&_[data-slot=tabs-trigger]:not([data-state=active])]:[&>:not(svg)]:hidden @max-[44rem]/tabs:[&_[data-slot=tabs-trigger]:not([data-state=active])]:[&_svg]:mr-0!",
  },
  9: {
    select: "hidden @max-[29rem]/tabs:flex",
    list: "@max-[29rem]/tabs:hidden @max-[50rem]/tabs:[&_[data-slot=tabs-trigger]:not([data-state=active])]:px-2! @max-[50rem]/tabs:[&_[data-slot=tabs-trigger]:not([data-state=active])]:text-[0px] @max-[50rem]/tabs:[&_[data-slot=tabs-trigger]:not([data-state=active])]:[&>:not(svg)]:hidden @max-[50rem]/tabs:[&_[data-slot=tabs-trigger]:not([data-state=active])]:[&_svg]:mr-0!",
  },
  10: {
    select: "hidden @max-[32rem]/tabs:flex",
    list: "@max-[32rem]/tabs:hidden @max-[56rem]/tabs:[&_[data-slot=tabs-trigger]:not([data-state=active])]:px-2! @max-[56rem]/tabs:[&_[data-slot=tabs-trigger]:not([data-state=active])]:text-[0px] @max-[56rem]/tabs:[&_[data-slot=tabs-trigger]:not([data-state=active])]:[&>:not(svg)]:hidden @max-[56rem]/tabs:[&_[data-slot=tabs-trigger]:not([data-state=active])]:[&_svg]:mr-0!",
  },
  11: {
    select: "hidden @max-[35rem]/tabs:flex",
    list: "@max-[35rem]/tabs:hidden @max-[61rem]/tabs:[&_[data-slot=tabs-trigger]:not([data-state=active])]:px-2! @max-[61rem]/tabs:[&_[data-slot=tabs-trigger]:not([data-state=active])]:text-[0px] @max-[61rem]/tabs:[&_[data-slot=tabs-trigger]:not([data-state=active])]:[&>:not(svg)]:hidden @max-[61rem]/tabs:[&_[data-slot=tabs-trigger]:not([data-state=active])]:[&_svg]:mr-0!",
  },
  12: {
    select: "hidden @max-[38rem]/tabs:flex",
    list: "@max-[38rem]/tabs:hidden @max-[67rem]/tabs:[&_[data-slot=tabs-trigger]:not([data-state=active])]:px-2! @max-[67rem]/tabs:[&_[data-slot=tabs-trigger]:not([data-state=active])]:text-[0px] @max-[67rem]/tabs:[&_[data-slot=tabs-trigger]:not([data-state=active])]:[&>:not(svg)]:hidden @max-[67rem]/tabs:[&_[data-slot=tabs-trigger]:not([data-state=active])]:[&_svg]:mr-0!",
  },
  13: {
    select: "hidden @max-[40rem]/tabs:flex",
    list: "@max-[40rem]/tabs:hidden @max-[72rem]/tabs:[&_[data-slot=tabs-trigger]:not([data-state=active])]:px-2! @max-[72rem]/tabs:[&_[data-slot=tabs-trigger]:not([data-state=active])]:text-[0px] @max-[72rem]/tabs:[&_[data-slot=tabs-trigger]:not([data-state=active])]:[&>:not(svg)]:hidden @max-[72rem]/tabs:[&_[data-slot=tabs-trigger]:not([data-state=active])]:[&_svg]:mr-0!",
  },
  14: {
    select: "hidden @max-[43rem]/tabs:flex",
    list: "@max-[43rem]/tabs:hidden @max-[78rem]/tabs:[&_[data-slot=tabs-trigger]:not([data-state=active])]:px-2! @max-[78rem]/tabs:[&_[data-slot=tabs-trigger]:not([data-state=active])]:text-[0px] @max-[78rem]/tabs:[&_[data-slot=tabs-trigger]:not([data-state=active])]:[&>:not(svg)]:hidden @max-[78rem]/tabs:[&_[data-slot=tabs-trigger]:not([data-state=active])]:[&_svg]:mr-0!",
  },
  15: {
    select: "hidden @max-[46rem]/tabs:flex",
    list: "@max-[46rem]/tabs:hidden @max-[83rem]/tabs:[&_[data-slot=tabs-trigger]:not([data-state=active])]:px-2! @max-[83rem]/tabs:[&_[data-slot=tabs-trigger]:not([data-state=active])]:text-[0px] @max-[83rem]/tabs:[&_[data-slot=tabs-trigger]:not([data-state=active])]:[&>:not(svg)]:hidden @max-[83rem]/tabs:[&_[data-slot=tabs-trigger]:not([data-state=active])]:[&_svg]:mr-0!",
  },
  16: {
    select: "hidden @max-[49rem]/tabs:flex",
    list: "@max-[49rem]/tabs:hidden @max-[89rem]/tabs:[&_[data-slot=tabs-trigger]:not([data-state=active])]:px-2! @max-[89rem]/tabs:[&_[data-slot=tabs-trigger]:not([data-state=active])]:text-[0px] @max-[89rem]/tabs:[&_[data-slot=tabs-trigger]:not([data-state=active])]:[&>:not(svg)]:hidden @max-[89rem]/tabs:[&_[data-slot=tabs-trigger]:not([data-state=active])]:[&_svg]:mr-0!",
  },
} as const satisfies Record<number, TabsTier>;

type TabsBucket = keyof typeof TABS_TIERS;

const MIN_TIER_TABS = 3;
const MAX_TIER_TABS = 16;

/** Nº de abas -> chave do mapa de limiares (clamp em 3..16). */
function getTabsBucket(tabCount: number): TabsBucket {
  return Math.min(Math.max(tabCount, MIN_TIER_TABS), MAX_TIER_TABS) as TabsBucket;
}

/**
 * Classes de tier de uma lista horizontal com `tabCount` abas (exportado p/ teste).
 * Com `iconTier` o Select só aparece abaixo do tier de ícones; a lista soma as classes do
 * compacto (mapa base) e as do tier de ícones.
 */
function getTabsTier(tabCount: number, iconTier = false): TabsTier {
  const bucket = getTabsBucket(tabCount);
  const base = TABS_TIERS[bucket];
  if (!iconTier) return base;
  const icons = TABS_ICON_TIERS[bucket];
  const compactOnly = base.list.replace(/@max-\[\d+rem\]\/tabs:hidden /, "");
  return { select: icons.select, list: `${compactOnly} ${icons.list}` };
}

type TabsValueContextValue = {
  orientation: "horizontal" | "vertical";
  value: string | undefined;
  setValue: (value: string) => void;
};

const TabsValueContext = React.createContext<TabsValueContextValue | null>(null);

function Tabs({
  className,
  orientation = "horizontal",
  value,
  defaultValue,
  onValueChange,
  ...props
}: React.ComponentProps<typeof TabsPrimitive.Root>) {
  // O espelho DIRIGE o Radix (`value={current}`), não só o acompanha. O Select do mobile
  // não é um `TabsTrigger`: ele chama `setValue` daqui. Enquanto o Root ficava em
  // `defaultValue`, o estado interno do Radix só mudava por clique num trigger — o call
  // site NÃO controlado (`<Tabs defaultValue="…">`) trocava o rótulo do Select e continuava
  // exibindo o painel da primeira aba. O controlado funcionava por acidente: o
  // `onValueChange` subia pro `useState` do call site e voltava como `value`. Com o mirror
  // no comando os dois modos andam igual.
  const [uncontrolled, setUncontrolled] = React.useState(defaultValue);
  const current = value ?? uncontrolled;

  const setValue = React.useCallback(
    (next: string) => {
      if (value === undefined) setUncontrolled(next);
      onValueChange?.(next);
    },
    [value, onValueChange]
  );

  const tabsValue = React.useMemo(
    () => ({ orientation, value: current, setValue }),
    [orientation, current, setValue]
  );

  return (
    <TabsValueContext value={tabsValue}>
      <TabsPrimitive.Root
        data-slot="tabs"
        data-orientation={orientation}
        className={cn(
          "group/tabs flex gap-2 data-horizontal:@container/tabs data-horizontal:w-full data-horizontal:min-w-0 data-horizontal:flex-col",
          className
        )}
        value={current}
        defaultValue={defaultValue}
        onValueChange={setValue}
        {...props}
      />
    </TabsValueContext>
  );
}

const tabsListVariants = cva(
  "group/tabs-list inline-flex w-fit items-center justify-center rounded-lg p-[3px] text-muted-foreground group-data-horizontal/tabs:min-h-8 group-data-horizontal/tabs:flex-nowrap group-data-horizontal/tabs:pointer-coarse:min-h-9 group-data-vertical/tabs:h-fit group-data-vertical/tabs:flex-col data-[variant=line]:rounded-none",
  {
    variants: {
      variant: {
        default: "bg-muted",
        line: "gap-1 bg-transparent",
        ghost: "gap-1 bg-transparent p-0",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
);

type TabItem = {
  value: string;
  label: React.ReactNode;
  disabled?: boolean;
};

/**
 * Lê os triggers da árvore para espelhá-los no Select.
 *
 * Desce em fragments, arrays e wrappers finos (`SandboxTabsTrigger`,
 * `TooltipTrigger asChild`) — o critério é ter `value` string, não ser
 * literalmente `TabsTrigger`.
 */
function collectTabItems(children: React.ReactNode): TabItem[] {
  const items: TabItem[] = [];

  const walk = (nodes: React.ReactNode) => {
    React.Children.forEach(nodes, (child) => {
      if (!React.isValidElement(child)) return;
      const childProps = child.props as {
        value?: unknown;
        disabled?: boolean;
        children?: React.ReactNode;
      };
      if (typeof childProps.value === "string") {
        items.push({
          value: childProps.value,
          label: childProps.children,
          disabled: childProps.disabled,
        });
        return;
      }
      walk(childProps.children);
    });
  };

  walk(children);
  return items;
}

function TabsList({
  className,
  variant = "default",
  mobile = "select",
  iconTier = false,
  selectClassName,
  children,
  ...props
}: React.ComponentProps<typeof TabsPrimitive.List> &
  VariantProps<typeof tabsListVariants> & {
    /** `"strip"` mantém a tira no mobile — só para aba ícone-only ou rótulo de 1 palavra. */
    mobile?: "select" | "strip";
    /**
     * Só quando TODA aba tem ícone: antes do Select, as inativas viram só-ícone (a ativa mantém
     * rótulo). Sem ícone o rótulo sumiria e a aba ficaria ilegível — nesse caso não passe.
     */
    iconTier?: boolean;
    /**
     * Classe do trigger do Select (mobile). `className` NÃO serve: ele estiliza a tira
     * (`flex-wrap`, `gap`, `h-auto`) e não faz sentido no combobox. Use quando a lista
     * divide uma linha flex com um vizinho e `w-full` esmagaria o vizinho.
     */
    selectClassName?: string;
  }) {
  const tabs = React.useContext(TabsValueContext);
  const items = React.useMemo(() => collectTabItems(children), [children]);
  const asSelect = mobile === "select" && tabs !== null && items.length >= MOBILE_SELECT_MIN_TABS;
  const isVertical = tabs?.orientation === "vertical";
  const tier = getTabsTier(items.length, iconTier);

  return (
    <>
      {asSelect && (
        <Select value={tabs.value ?? ""} onValueChange={tabs.setValue}>
          <SelectTrigger
            className={cn("w-full", isVertical ? "md:hidden" : tier.select, selectClassName)}
            aria-label={props["aria-label"]}
          >
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {items.map((item) => (
              <SelectItem key={item.value} value={item.value} disabled={item.disabled}>
                <span className="flex items-center gap-2">{item.label}</span>
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      )}
      <TabsPrimitive.List
        data-slot="tabs-list"
        data-variant={variant}
        className={cn(
          tabsListVariants({ variant }),
          asSelect && (isVertical ? "max-md:hidden" : tier.list),
          className
        )}
        {...props}
      >
        {children}
      </TabsPrimitive.List>
    </>
  );
}

/** Texto puro dos filhos (rótulo) para o `title` do tier só-ícone; "" se não houver string. */
function textOf(node: React.ReactNode): string {
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(textOf).join("");
  return "";
}

function TabsTrigger({ className, ...props }: React.ComponentProps<typeof TabsPrimitive.Trigger>) {
  return (
    <TabsPrimitive.Trigger
      data-slot="tabs-trigger"
      title={textOf(props.children).trim() || undefined}
      className={cn(
        "text-foreground/60 hover:text-foreground focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:outline-ring dark:text-muted-foreground dark:hover:text-foreground relative inline-flex h-[calc(100%-1px)] min-h-[25px] flex-none items-center justify-center gap-1.5 rounded-md border border-transparent px-1.5 py-0.5 text-xs font-medium whitespace-nowrap transition-all group-data-vertical/tabs:w-full group-data-vertical/tabs:justify-start group-data-vertical/tabs:py-[calc(--spacing(1.25))] focus-visible:ring-[3px] focus-visible:outline-1 disabled:pointer-events-none disabled:opacity-50 has-data-[icon=inline-end]:pr-1 has-data-[icon=inline-start]:pl-1 pointer-coarse:min-h-9 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-3.5",
        "group-data-[variant=line]/tabs-list:bg-transparent group-data-[variant=line]/tabs-list:data-active:bg-transparent dark:group-data-[variant=line]/tabs-list:data-active:border-transparent dark:group-data-[variant=line]/tabs-list:data-active:bg-transparent",
        "data-active:bg-background data-active:text-foreground dark:data-active:border-input dark:data-active:bg-input/30 dark:data-active:text-foreground",
        // ghost: transparent triggers, subtle fill on hover, solid fill when active (Gemini/GPT style)
        "group-data-[variant=ghost]/tabs-list:hover:bg-accent/50 group-data-[variant=ghost]/tabs-list:data-active:bg-accent group-data-[variant=ghost]/tabs-list:data-active:text-accent-foreground dark:group-data-[variant=ghost]/tabs-list:data-active:bg-accent group-data-[variant=ghost]/tabs-list:rounded-lg group-data-[variant=ghost]/tabs-list:px-3 group-data-[variant=ghost]/tabs-list:py-1.5 group-data-[variant=ghost]/tabs-list:data-active:shadow-none dark:group-data-[variant=ghost]/tabs-list:data-active:border-transparent",
        "after:bg-foreground after:absolute after:opacity-0 after:transition-opacity group-data-horizontal/tabs:after:inset-x-0 group-data-horizontal/tabs:after:bottom-[-5px] group-data-horizontal/tabs:after:h-0.5 group-data-vertical/tabs:after:inset-y-0 group-data-vertical/tabs:after:-right-1 group-data-vertical/tabs:after:w-0.5 group-data-[variant=line]/tabs-list:data-active:after:opacity-100",
        className
      )}
      {...props}
    />
  );
}

function TabsContent({ className, ...props }: React.ComponentProps<typeof TabsPrimitive.Content>) {
  return (
    <TabsPrimitive.Content
      data-slot="tabs-content"
      className={cn("flex-1 text-xs/relaxed outline-none", className)}
      {...props}
    />
  );
}

export { Tabs, TabsList, TabsTrigger, TabsContent, tabsListVariants, getTabsTier };
