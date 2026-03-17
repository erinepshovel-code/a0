import { cn } from "@/lib/utils";
import { usePersona, type Persona } from "@/hooks/use-persona";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Check, Briefcase, FlaskConical, Landmark, User } from "lucide-react";

const PERSONAS: Array<{
  id: Persona;
  label: string;
  icon: any;
  tagline: string;
  accent: string;
  features: string[];
}> = [
  {
    id: "free",
    label: "Free",
    icon: User,
    tagline: "Default agent experience",
    accent: "border-border",
    features: [
      "Agent + Tools console",
      "Standard EDCM analysis",
      "General-purpose system prompt",
    ],
  },
  {
    id: "legal",
    label: "Legal",
    icon: Briefcase,
    tagline: "For legal & compliance work",
    accent: "border-amber-500/60",
    features: [
      "Full console access",
      "Legal EDCM terminology",
      "Risk & exposure framing",
    ],
  },
  {
    id: "researcher",
    label: "Researcher",
    icon: FlaskConical,
    tagline: "For academic & analysis work",
    accent: "border-blue-500/60",
    features: [
      "Full console access",
      "Methodology-focused framing",
      "Confidence & confound flagging",
    ],
  },
  {
    id: "political",
    label: "Political",
    icon: Landmark,
    tagline: "For civic & political strategy",
    accent: "border-purple-500/60",
    features: [
      "Full console access",
      "Stakeholder-framed analysis",
      "Messaging & coalition lens",
    ],
  },
];

export default function PricingPage() {
  const { persona, setPersona, isPending } = usePersona();

  return (
    <ScrollArea className="h-full">
      <div className="px-4 py-6 space-y-5 pb-safe max-w-lg mx-auto">
        <div>
          <h1 className="text-lg font-semibold" data-testid="text-pricing-title">View Mode</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Select the lens that fits your work. Affects console tabs, EDCM labels, and system prompt framing.
          </p>
        </div>

        <div className="space-y-3">
          {PERSONAS.map((p) => {
            const Icon = p.icon;
            const selected = persona === p.id;
            return (
              <button
                key={p.id}
                onClick={() => setPersona(p.id)}
                disabled={isPending}
                data-testid={`persona-card-${p.id}`}
                className={cn(
                  "w-full text-left rounded-xl border-2 p-4 transition-all active:scale-[0.99]",
                  selected ? `${p.accent} bg-muted/40` : "border-border bg-background"
                )}
              >
                <div className="flex items-start gap-3">
                  <div className={cn("rounded-lg p-2 mt-0.5 flex-shrink-0", selected ? "bg-primary/10" : "bg-muted")}>
                    <Icon className={cn("w-4 h-4", selected ? "text-primary" : "text-muted-foreground")} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-semibold text-sm">{p.label}</span>
                      {selected && <Check className="w-4 h-4 text-primary flex-shrink-0" data-testid={`icon-persona-selected-${p.id}`} />}
                    </div>
                    <p className="text-xs text-muted-foreground mt-0.5">{p.tagline}</p>
                    <ul className="mt-2 space-y-1">
                      {p.features.map((f) => (
                        <li key={f} className="text-xs text-muted-foreground flex items-center gap-1.5">
                          <span className="w-1 h-1 rounded-full bg-muted-foreground/40 flex-shrink-0" />
                          {f}
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              </button>
            );
          })}
        </div>

        {persona !== "free" && (
          <p className="text-[11px] text-muted-foreground text-center" data-testid="text-persona-active">
            Active: <span className="font-semibold capitalize">{persona}</span> lens
          </p>
        )}
      </div>
    </ScrollArea>
  );
}
