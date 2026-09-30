import { cn } from "@/lib/utils";
import { memo } from "react";
import type { ComponentProps } from "react";
import { Streamdown } from "streamdown";

interface MarkdownPreviewProps {
  source: string;
  className?: string;
  emptyHint?: string;
}

const HEADING_CLASSES: Record<number, string> = {
  1: "text-base font-semibold text-foreground mt-4 mb-2 first:mt-0",
  2: "text-sm font-semibold text-foreground mt-4 mb-2 first:mt-0",
  3: "text-xs font-semibold uppercase tracking-wide text-muted-foreground mt-3 mb-1 first:mt-0",
};

type HeadingProps = ComponentProps<"h1"> & { node?: unknown };

function heading(level: 1 | 2 | 3) {
  return function Heading({ className, node: _node, ...props }: HeadingProps) {
    return <p className={cn(HEADING_CLASSES[level], className)} {...props} />;
  };
}

function Paragraph({ className, node: _node, ...props }: ComponentProps<"p"> & { node?: unknown }) {
  return <p className={cn("text-foreground/90 text-xs/relaxed", className)} {...props} />;
}

function UnorderedList({
  className,
  node: _node,
  ...props
}: ComponentProps<"ul"> & { node?: unknown }) {
  return (
    <ul
      className={cn(
        "text-foreground/90 my-1 list-disc space-y-0.5 pl-5 text-xs/relaxed",
        className
      )}
      {...props}
    />
  );
}

function OrderedList({
  className,
  node: _node,
  ...props
}: ComponentProps<"ol"> & { node?: unknown }) {
  return (
    <ol
      className={cn(
        "text-foreground/90 my-1 list-decimal space-y-0.5 pl-5 text-xs/relaxed",
        className
      )}
      {...props}
    />
  );
}

function ListItem({ className, node: _node, ...props }: ComponentProps<"li"> & { node?: unknown }) {
  return <li className={cn("[&>p]:inline", className)} {...props} />;
}

function Strong({
  className,
  node: _node,
  ...props
}: ComponentProps<"strong"> & { node?: unknown }) {
  return <strong className={cn("text-foreground font-semibold", className)} {...props} />;
}

/**
 * Thin Streamdown wrapper that renders the saved agent-instructions Markdown as compact prose.
 * Streamdown is the standard Markdown renderer (never a home-made parser).
 */
export const MarkdownPreview = memo(function MarkdownPreview({
  source,
  className,
  emptyHint,
}: MarkdownPreviewProps) {
  if (!source.trim()) {
    return (
      <p className={cn("text-muted-foreground text-xs/relaxed italic", className)}>
        {emptyHint ?? "Nada para visualizar ainda."}
      </p>
    );
  }

  return (
    <Streamdown
      className={cn("[&>*:first-child]:mt-0 [&>*:last-child]:mb-0", className)}
      components={{
        h1: heading(1),
        h2: heading(2),
        h3: heading(3),
        p: Paragraph,
        ul: UnorderedList,
        ol: OrderedList,
        li: ListItem,
        strong: Strong,
      }}
    >
      {source}
    </Streamdown>
  );
});
