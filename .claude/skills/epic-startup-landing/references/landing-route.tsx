/**
 * Reference: src/routes/index.tsx — the public epic-startup landing (from
 * the reference frontend). Full-screen, no app shell, single CTA → /login. Adapt the
 * wordmark, subtitle, eyebrow signature, and accent colors per project; keep
 * the layering (Particles → glow → vignette → content) and the contract.
 */

import { createFileRoute, Link, redirect } from "@tanstack/react-router";
import { ArrowRight } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Particles } from "@/components/ui/particles";
import { useAuthStore } from "@/stores/auth";

export const Route = createFileRoute("/")({
  beforeLoad: () => {
    if (useAuthStore.getState().accessToken) {
      throw redirect({ to: "/app/dashboard" });
    }
  },
  component: LandingPage,
});

// Product-specific signature detail — adapt or replace per project.
const LAYER_DOTS = ["bg-bronze", "bg-silver", "bg-gold"];

function LandingPage() {
  return (
    <div className="dark relative min-h-screen w-full overflow-hidden bg-background text-foreground">
      {/* Drifting particle field */}
      <Particles
        className="absolute inset-0 z-0"
        quantity={140}
        ease={70}
        staticity={40}
        color="#ffffff"
      />

      {/* Soft radial glow behind the wordmark for depth */}
      <div
        aria-hidden
        className="pointer-events-none absolute top-1/2 left-1/2 z-0 size-[820px] -translate-x-1/2 -translate-y-1/2 rounded-full opacity-70 blur-3xl"
        style={{
          background:
            "radial-gradient(circle, color-mix(in oklch, var(--foreground) 13%, transparent) 0%, transparent 70%)",
        }}
      />

      {/* Edge vignette — pulls focus to the center */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 z-0"
        style={{
          background:
            "radial-gradient(ellipse at center, transparent 38%, var(--background) 100%)",
        }}
      />

      <main className="relative z-10 flex min-h-screen flex-col items-center justify-center px-6 text-center">
        <div
          className="flex animate-in items-center gap-2.5 fade-in-0 slide-in-from-bottom-2 duration-700 fill-mode-both"
          style={{ animationDelay: "0ms" }}
        >
          <div className="flex items-center gap-1">
            {LAYER_DOTS.map((dot) => (
              <span key={dot} className={`size-1.5 rounded-full ${dot}`} />
            ))}
          </div>
          <span className="text-xs font-medium tracking-[0.25em] text-muted-foreground uppercase">
            Plataforma de Dados
          </span>
        </div>

        <h1
          className="mt-6 animate-in text-6xl font-bold tracking-tight fade-in-0 slide-in-from-bottom-3 duration-700 fill-mode-both sm:text-7xl md:text-8xl"
          style={{ animationDelay: "100ms" }}
        >
          App{" "}
          <span className="bg-linear-to-r from-bronze via-silver to-gold bg-clip-text text-transparent">
            Name
          </span>
        </h1>

        <p
          className="mt-5 max-w-xl animate-in text-base text-balance text-muted-foreground fade-in-0 slide-in-from-bottom-3 duration-700 fill-mode-both sm:text-lg"
          style={{ animationDelay: "200ms" }}
        >
          Catálogo, linhagem e controle de acesso — Bronze, Silver e Gold numa só
          plataforma.
        </p>

        <div
          className="mt-9 animate-in fade-in-0 slide-in-from-bottom-3 duration-700 fill-mode-both"
          style={{ animationDelay: "300ms" }}
        >
          <Button size="lg" asChild className="group h-11 px-6 text-base">
            <Link to="/login">
              Começar
              <ArrowRight
                data-icon="inline-end"
                className="transition-transform group-hover:translate-x-0.5"
              />
            </Link>
          </Button>
        </div>
      </main>
    </div>
  );
}
