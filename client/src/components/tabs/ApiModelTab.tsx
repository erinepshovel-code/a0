import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "@/lib/queryClient";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/hooks/use-toast";
import { cn } from "@/lib/utils";
import { Check, Eye, EyeOff, Zap } from "lucide-react";

type SlotData = { label: string; provider: string; model: string; baseUrl: string; apiKeySet: boolean };
type RegistryModel = { id: string; name: string; contextWindow: number; maxOutput: number };
type RegistryProvider = {
  name: string; label: string; baseURL: string; nativeIntegration: boolean;
  authHeader: string; requestFormat: string; notes: string;
  models: RegistryModel[];
};

const SLOT_COLORS: Record<string, string> = {
  a: "bg-blue-500 text-white border-blue-600",
  b: "bg-orange-500 text-white border-orange-600",
  c: "bg-purple-500 text-white border-purple-600",
};
const SLOT_OUTLINE: Record<string, string> = {
  a: "border-blue-400/50 text-blue-400 hover:bg-blue-500/10",
  b: "border-orange-400/50 text-orange-400 hover:bg-orange-500/10",
  c: "border-purple-400/50 text-purple-400 hover:bg-purple-500/10",
};

function fmtCtx(n: number) {
  if (n >= 1000000) return `${(n / 1000000).toFixed(0)}M`;
  if (n >= 1000) return `${(n / 1000).toFixed(0)}K`;
  return String(n);
}

export function ApiModelTab() {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [activeProvider, setActiveProvider] = useState<string | null>(null);
  const [apiKeys, setApiKeys] = useState<Record<string, string>>({});
  const [showKey, setShowKey] = useState<Record<string, boolean>>({});

  const { data: slots = {} } = useQuery<Record<string, SlotData>>({
    queryKey: ["/api/v1/agent/slots"],
  });

  const { data: registry, isLoading: regLoading } = useQuery<{ providers: RegistryProvider[] }>({
    queryKey: ["/api/v1/model-registry"],
    staleTime: 30000,
  });

  const assignMutation = useMutation({
    mutationFn: ({ slotKey, provider, model, baseUrl }: { slotKey: string; provider: string; model: string; baseUrl: string }) =>
      apiRequest("PATCH", `/api/agent/slots/${slotKey}`, { provider, model, baseUrl, label: slotKey.toUpperCase() }),
    onSuccess: (_, { slotKey, model }) => {
      queryClient.invalidateQueries({ queryKey: ["/api/v1/agent/slots"] });
      toast({ title: `Slot ${slotKey.toUpperCase()} → ${model}` });
    },
    onError: (e: any) => toast({ title: "Error", description: e.message, variant: "destructive" }),
  });

  const keyMutation = useMutation({
    mutationFn: ({ slotKey, apiKey }: { slotKey: string; apiKey: string }) =>
      apiRequest("PATCH", `/api/agent/slots/${slotKey}`, { apiKey }),
    onSuccess: (_, { slotKey }) => {
      queryClient.invalidateQueries({ queryKey: ["/api/v1/agent/slots"] });
      setApiKeys(prev => ({ ...prev, [slotKey]: "" }));
      toast({ title: `Key stored for slot ${slotKey.toUpperCase()}` });
    },
    onError: (e: any) => toast({ title: "Error", description: e.message, variant: "destructive" }),
  });

  const providers = registry?.providers ?? [];
  const displayProviders = activeProvider ? providers.filter(p => p.name === activeProvider) : providers;

  function modelSlots(providerName: string, modelId: string): string[] {
    return (["a", "b", "c"] as const).filter(
      s => slots[s]?.provider === providerName && slots[s]?.model === modelId
    );
  }

  function handleAssign(slotKey: string, prov: RegistryProvider, model: RegistryModel) {
    assignMutation.mutate({ slotKey, provider: prov.name, model: model.id, baseUrl: prov.baseURL });
  }

  const SLOT_KEYS = ["a", "b", "c"] as const;

  return (
    <div className="h-full w-full overflow-y-auto overflow-x-hidden px-3 py-3 space-y-4">

      {/* Current slot summary */}
      <div className="rounded-lg border border-border bg-card p-3 space-y-2">
        <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Active Slots</h4>
        <div className="grid grid-cols-3 gap-2">
          {SLOT_KEYS.map(s => (
            <div key={s} className="space-y-1">
              <div className={cn("text-center rounded px-1 py-0.5 text-[10px] font-bold border", SLOT_COLORS[s])}>
                {s.toUpperCase()}
              </div>
              {slots[s] ? (
                <>
                  <p className="text-[9px] font-mono text-center text-foreground truncate">{slots[s].model}</p>
                  <p className="text-[8px] text-center text-muted-foreground capitalize">{slots[s].provider}</p>
                </>
              ) : (
                <p className="text-[9px] text-center text-muted-foreground">unset</p>
              )}
              {/* Key input for this slot */}
              <div className="flex gap-0.5">
                <div className="relative flex-1">
                  <Input
                    type={showKey[s] ? "text" : "password"}
                    value={apiKeys[s] ?? ""}
                    onChange={e => setApiKeys(prev => ({ ...prev, [s]: e.target.value }))}
                    placeholder={slots[s]?.apiKeySet ? "••••" : "key…"}
                    className="h-5 text-[9px] font-mono pr-5 pl-1"
                    data-testid={`input-slot-${s}-key`}
                  />
                  <button className="absolute right-1 top-1/2 -translate-y-1/2 text-muted-foreground" onClick={() => setShowKey(prev => ({ ...prev, [s]: !prev[s] }))}>
                    {showKey[s] ? <EyeOff className="w-2.5 h-2.5" /> : <Eye className="w-2.5 h-2.5" />}
                  </button>
                </div>
                {apiKeys[s] && (
                  <Button size="sm" className="h-5 px-1" onClick={() => keyMutation.mutate({ slotKey: s, apiKey: apiKeys[s] })}>
                    <Check className="w-2.5 h-2.5" />
                  </Button>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Provider filter tabs */}
      <div className="flex gap-1 flex-wrap">
        <button
          onClick={() => setActiveProvider(null)}
          className={cn("px-2 py-0.5 rounded border text-[10px] transition-colors", !activeProvider ? "border-primary bg-primary/10 text-primary" : "border-border text-muted-foreground hover:border-primary/40")}
          data-testid="filter-all"
        >
          All
        </button>
        {providers.map(p => (
          <button
            key={p.name}
            onClick={() => setActiveProvider(activeProvider === p.name ? null : p.name)}
            className={cn(
              "px-2 py-0.5 rounded border text-[10px] transition-colors flex items-center gap-1",
              activeProvider === p.name ? "border-primary bg-primary/10 text-primary" : "border-border text-muted-foreground hover:border-primary/40"
            )}
            data-testid={`filter-${p.name}`}
          >
            {p.nativeIntegration && <Zap className="w-2.5 h-2.5 text-green-500" />}
            {p.label}
          </button>
        ))}
      </div>

      {regLoading && <Skeleton className="h-40 w-full" />}

      {/* Model cards */}
      {displayProviders.map(prov => (
        <div key={prov.name} className="space-y-2">
          <div className="flex items-center gap-2">
            <h4 className="text-xs font-semibold">{prov.label}</h4>
            {prov.nativeIntegration && (
              <Badge variant="outline" className="text-[9px] text-green-500 border-green-500/40 gap-1">
                <Zap className="w-2.5 h-2.5" /> native
              </Badge>
            )}
            <span className="text-[9px] text-muted-foreground font-mono truncate flex-1">{prov.baseURL}</span>
          </div>
          <div className="grid gap-2">
            {prov.models.map(model => {
              const assigned = modelSlots(prov.name, model.id);
              return (
                <div
                  key={model.id}
                  className={cn(
                    "rounded-lg border p-2.5 transition-colors",
                    assigned.length > 0 ? "border-primary/30 bg-primary/5" : "border-border bg-card"
                  )}
                  data-testid={`model-card-${prov.name}-${model.id}`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0 flex-1">
                      <p className="text-xs font-medium truncate">{model.name}</p>
                      <p className="text-[9px] font-mono text-muted-foreground truncate">{model.id}</p>
                      <p className="text-[9px] text-muted-foreground mt-0.5">
                        {fmtCtx(model.contextWindow)} ctx · {fmtCtx(model.maxOutput)} out
                      </p>
                    </div>
                    <div className="flex flex-col gap-1 shrink-0">
                      <div className="flex gap-1">
                        {SLOT_KEYS.map(s => {
                          const isAssigned = assigned.includes(s);
                          return (
                            <button
                              key={s}
                              onClick={() => handleAssign(s, prov, model)}
                              className={cn(
                                "w-7 h-7 rounded border text-[10px] font-bold transition-all",
                                isAssigned ? SLOT_COLORS[s] : `border bg-background ${SLOT_OUTLINE[s]}`
                              )}
                              title={isAssigned ? `Remove from slot ${s.toUpperCase()}` : `Assign to slot ${s.toUpperCase()}`}
                              data-testid={`assign-${s}-${prov.name}-${model.id}`}
                            >
                              {s.toUpperCase()}
                            </button>
                          );
                        })}
                      </div>
                      {assigned.length > 0 && (
                        <div className="flex gap-1 justify-end">
                          {assigned.map(s => (
                            <Badge key={s} className={cn("text-[8px] px-1", SLOT_COLORS[s])}>
                              {s.toUpperCase()}
                            </Badge>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
