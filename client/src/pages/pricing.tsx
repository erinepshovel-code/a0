import { cn } from "@/lib/utils";
import { usePersona, PERSONA_LABELS, PERSONA_DESCRIPTIONS, PERSONA_ICONS, type Persona } from "@/hooks/use-persona";
import { Check, Loader2 } from "lucide-react";
import { ScrollArea } from "@/components/ui/scroll-area";

const PERSONAS: Persona[] = ["free", "legal", "researcher", "political"];

const PERSONA_FEATURES: Record<Persona, string[]> = {
  free: [
    "Agent workflow & run control",
    "Cost metrics",
    "System settings & logs",
    "Tool executor & file context",
    "Model slot switching (A/B/C)",
  ],
  legal: [
    "Everything in Free",
    "EDCM with legal metric labels",
    "Memory & semantic seeds",
    "Compliance Margin · Due Diligence · Risk Drift",
    "Document Variance · Integrity Index · Tribunal Backfire",
    "Brain trajectory view",
  ],
  researcher: [
    "Everything in Legal",
    "Full Triad: Psi Ψ · Omega Ω · Heartbeat",
    "EDCM with research metric labels",
    "Concept Drift · Data Accuracy · Interpretability",
    "Bandit arm optimizer",
    "Credential vault",
  ],
  political: [
    "Everything in Legal",
    "Full Triad: Psi Ψ · Omega Ω · Heartbeat",
    "EDCM with political metric labels",
    "Campaign Momentum · Narrative Drift · Demographic Alignment",
    "Division Score · Influence Trajectory · Tactical Backfire",
    "Bandit arm optimizer",
  ],
};

const PERSONA_COLOR: Record<Persona, string> = {
  free: "border-border",
  legal: "border-blue-500/60",
  researcher: "border-purple-500/60",
  political: "border-emerald-500/60",
};

const PERSONA_ACCENT: Record<Persona, string> = {
  free: "text-muted-foreground",
  legal: "text-blue-400",
  researcher: "text-purple-400",
  political: "text-emerald-400",
};

const PERSONA_BG: Record<Persona, string> = {
  free: "",
  legal: "bg-blue-500/5",
  researcher: "bg-purple-500/5",
  political: "bg-emerald-500/5",
};

export default function PricingPage() {
  const { persona: active, setPersona, isPending, isLoading } = usePersona();

  return (
    <div className="flex flex-col h-full">
      <header className="flex items-center gap-2 px-4 py-3 border-b border-border bg-card flex-shrink-0">
        <span className="font-semibold text-sm">Persona</span>
        {isLoading && <Loader2 className="w-3.5 h-3.5 animate-spin text-muted-foreground" />}
        <span className="ml-auto text-[10px] text-muted-foreground font-mono">
          active: <span className="text-foreground">{active}</span>
        </span>
      </header>

      <ScrollArea className="flex-1">
        <div className="p-4 space-y-3 pb-8">
          <p className="text-xs text-muted-foreground">
            Your persona gates which console views are visible and how a0 frames its analysis. EDCM metric labels adapt per persona.
          </p>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {PERSONAS.map((p) => {
              const isActive = active === p;
              return (
                <button
                  key={p}
                  onClick={() => !isPending && setPersona(p)}
                  disabled={isPending}
                  data-testid={`persona-card-${p}`}
                  className={cn(
                    "text-left rounded-xl border p-4 transition-all select-none",
                    "hover:bg-card/80 active:scale-[0.98]",
                    PERSONA_COLOR[p],
                    PERSONA_BG[p],
                    isActive && "ring-2 ring-primary/60",
                    isPending && "opacity-60 cursor-not-allowed"
                  )}
                >
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <div className="flex items-center gap-2">
                      <span className="text-lg leading-none">{PERSONA_ICONS[p]}</span>
                      <span className={cn("font-semibold text-sm", isActive ? "text-foreground" : PERSONA_ACCENT[p])}>
                        {PERSONA_LABELS[p]}
                      </span>
                    </div>
                    {isActive && (
                      <span className="flex items-center gap-1 text-[10px] font-medium text-primary bg-primary/10 px-2 py-0.5 rounded-full flex-shrink-0">
                        <Check className="w-3 h-3" /> Active
                      </span>
                    )}
                  </div>

                  <p className="text-[11px] text-muted-foreground mb-3 leading-relaxed">
                    {PERSONA_DESCRIPTIONS[p]}
                  </p>

                  <ul className="space-y-1">
                    {PERSONA_FEATURES[p].map((f) => (
                      <li key={f} className="flex items-start gap-1.5 text-[10px] text-muted-foreground">
                        <Check className={cn("w-3 h-3 flex-shrink-0 mt-0.5", isActive ? "text-primary" : PERSONA_ACCENT[p])} />
                        <span>{f}</span>
                      </li>
                    ))}
                  </ul>
                </button>
              );
            })}
          </div>

          {isPending && (
            <div className="flex items-center gap-2 text-xs text-muted-foreground pt-1">
              <Loader2 className="w-3 h-3 animate-spin" />
              Switching persona…
            </div>
          )}
        </div>
      </ScrollArea>
    </div>
  );
}
