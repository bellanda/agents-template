/**
 * Tabs canônico — a tira vira `Select` abaixo de 768px.
 *
 * Vendorar em `components/ui/tabs.tsx`. O que é PADRÃO cross-projeto é o bloco
 * responsivo (`TabsValueContext` + `collectTabItems` + o dual-render do
 * `TabsList`); `tabsListVariants` e o `className` do `TabsTrigger` são
 * IDENTIDADE — mantenha os do projeto ao adotar.
 *
 * Doc: `references/responsive-tabs.md`.
 */
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
   Abas no mobile

   Abaixo de 768px uma tira de 3+ abas não cabe: ou os triggers estouram a
   largura (scroll horizontal na página inteira), ou o `flex-wrap` empilha e a
   tira come metade da tela. A partir de 3 abas a navegação vira `Select`.

   A troca é CSS (`md:hidden` / `max-md:hidden`) e as DUAS formas montam sempre.
   NUNCA `useIsMobile()` aqui: ele resolve em `useEffect`, então o primeiro
   frame no celular renderiza a tira e pisca — e a troca de árvore remonta o
   painel ativo.
   ════════════════════════════════════════════════════════════════════════════ */

/** A partir de 3 abas a tira não cabe em 375px. Com 2 ela cabe e o Select só atrapalha. */
const MOBILE_SELECT_MIN_TABS = 3;

type TabsValueContextValue = {
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
  // Espelho do valor ativo, só para o `TabsList` alimentar o Select do mobile.
  // `value`/`defaultValue` seguem intactos para o Root — quem manda no controle
  // continua sendo o Radix; aqui a gente só acompanha o que ele já decidiu.
  const [uncontrolled, setUncontrolled] = React.useState(defaultValue);
  const current = value ?? uncontrolled;

  const setValue = React.useCallback(
    (next: string) => {
      if (value === undefined) setUncontrolled(next);
      onValueChange?.(next);
    },
    [value, onValueChange]
  );

  const tabsValue = React.useMemo(() => ({ value: current, setValue }), [current, setValue]);

  return (
    <TabsValueContext value={tabsValue}>
      <TabsPrimitive.Root
        data-slot="tabs"
        data-orientation={orientation}
        className={cn("group/tabs flex gap-2 data-horizontal:flex-col", className)}
        value={value}
        defaultValue={defaultValue}
        onValueChange={setValue}
        {...props}
      />
    </TabsValueContext>
  );
}

/* IDENTIDADE — troque pelo cva do projeto ao vendorar. */
const tabsListVariants = cva(
  "group/tabs-list text-muted-foreground inline-flex w-fit items-center justify-center rounded-lg p-[3px] group-data-horizontal/tabs:h-8 group-data-vertical/tabs:h-fit group-data-vertical/tabs:flex-col data-[variant=line]:rounded-none",
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
  selectClassName,
  children,
  ...props
}: React.ComponentProps<typeof TabsPrimitive.List> &
  VariantProps<typeof tabsListVariants> & {
    /** `"strip"` mantém a tira no mobile — só para aba ícone-only ou rótulo de 1 palavra. */
    mobile?: "select" | "strip";
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

  return (
    <>
      {asSelect && (
        <Select value={tabs.value ?? ""} onValueChange={tabs.setValue}>
          <SelectTrigger
            className={cn("w-full md:hidden", selectClassName)}
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
        className={cn(tabsListVariants({ variant }), asSelect && "max-md:hidden", className)}
        {...props}
      >
        {children}
      </TabsPrimitive.List>
    </>
  );
}

/* IDENTIDADE — troque pelo className do projeto ao vendorar. */
function TabsTrigger({ className, ...props }: React.ComponentProps<typeof TabsPrimitive.Trigger>) {
  return (
    <TabsPrimitive.Trigger
      data-slot="tabs-trigger"
      className={cn(
        "text-foreground/60 hover:text-foreground focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:outline-ring dark:text-muted-foreground dark:hover:text-foreground relative inline-flex h-[calc(100%-1px)] flex-1 items-center justify-center gap-1.5 rounded-md border border-transparent px-1.5 py-0.5 text-xs font-medium whitespace-nowrap transition-all group-data-vertical/tabs:w-full group-data-vertical/tabs:justify-start focus-visible:ring-[3px] focus-visible:outline-1 disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-3.5",
        "data-active:bg-background data-active:text-foreground dark:data-active:border-input dark:data-active:bg-input/30 dark:data-active:text-foreground",
        "group-data-[variant=ghost]/tabs-list:hover:bg-accent/50 group-data-[variant=ghost]/tabs-list:data-active:bg-accent group-data-[variant=ghost]/tabs-list:data-active:text-accent-foreground group-data-[variant=ghost]/tabs-list:rounded-lg group-data-[variant=ghost]/tabs-list:px-3 group-data-[variant=ghost]/tabs-list:py-1.5 group-data-[variant=ghost]/tabs-list:data-active:shadow-none",
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
      className={cn("flex-1 outline-none", className)}
      {...props}
    />
  );
}

export { Tabs, TabsList, TabsTrigger, TabsContent, tabsListVariants };
