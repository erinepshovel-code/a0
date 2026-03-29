import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { queryClient, apiRequest } from "@/lib/queryClient";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { useToast } from "@/hooks/use-toast";
import { Cpu, MessageSquare, Zap, ChevronRight, Pencil, Check, X } from "lucide-react";

type ModelProvider = "pcna" | "gemini" | "xai" | "ollama";

interface ModelSlot {
  key: string;
  label: string;
  group: string;
  description: string;
  provider: ModelProvider;
  model: string;
  enabled: boolean;
}

const PROVIDER_COLORS: Record<ModelProvider, string> = {
  pcna: "bg-violet-500/20 text-violet-300 border-violet-500/40",
  gemini: "bg-blue-500/20 text-blue-300 border-blue-500/40",
  xai: "bg-orange-500/20 text-orange-300 border-orange-500/40",
  ollama: "bg-green-500/20 text-green-300 border-green-500/40",
};

const PROVIDER_MODELS: Record<ModelProvider, string[]> = {
  pcna: ["native"],
  gemini: ["gemini-2.5-flash-preview-04-17", "gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"],
  xai: ["grok-3-mini", "grok-3", "grok-beta"],
  ollama: ["llama3", "mistral", "deepseek-r1", "phi3"],
};

const GROUP_ICONS: Record<string, any> = {
  Heartbeat: Zap,
  Chat: MessageSquare,
  Synthesis: Cpu,
};

const FLOW_NODES = [
  { id: "user", label: "User Input", x: 20, y: 50, w: 80, h: 32, color: "#6b7280" },
  { id: "heartbeat", label: "Heartbeat", x: 160, y: 20, w: 90, h: 32, color: "#7c3aed" },
  { id: "chat", label: "Chat", x: 160, y: 65, w: 90, h: 32, color: "#2563eb" },
  { id: "pcna_hb", label: "PCNA Engine", x: 330, y: 20, w: 100, h: 32, color: "#7c3aed" },
  { id: "model_chat", label: "Model Slots A/B/C", x: 330, y: 65, w: 120, h: 32, color: "#2563eb" },
  { id: "synthesis", label: "Synthesis", x: 160, y: 115, w: 90, h: 32, color: "#0891b2" },
  { id: "output", label: "Response", x: 520, y: 65, w: 80, h: 32, color: "#6b7280" },
];

const FLOW_EDGES = [
  { from: "user", to: "heartbeat" },
  { from: "user", to: "chat" },
  { from: "heartbeat", to: "pcna_hb" },
  { from: "chat", to: "model_chat" },
  { from: "model_chat", to: "synthesis" },
  { from: "synthesis", to: "output" },
  { from: "pcna_hb", to: "synthesis" },
];

function FlowDiagram() {
  const getCenter = (node: typeof FLOW_NODES[0]) => ({
    cx: node.x + node.w / 2,
    cy: node.y + node.h / 2,
  });

  return (
    <div className="relative w-full overflow-x-auto">
      <svg viewBox="0 0 640 160" className="w-full h-36 min-w-[480px]" style={{ maxHeight: 144 }}>
        {FLOW_EDGES.map((e, i) => {
          const from = FLOW_NODES.find(n => n.id === e.from)!;
          const to = FLOW_NODES.find(n => n.id === e.to)!;
          const fc = getCenter(from);
          const tc = getCenter(to);
          return (
            <line key={i}
              x1={fc.cx} y1={fc.cy} x2={tc.cx} y2={tc.cy}
              stroke="#4b5563" strokeWidth="1.5" strokeDasharray="4 2"
              markerEnd="url(#arrow)"
            />
          );
        })}
        <defs>
          <marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
            <path d="M0,0 L0,6 L8,3 z" fill="#4b5563" />
          </marker>
        </defs>
        {FLOW_NODES.map(n => (
          <g key={n.id}>
            <rect x={n.x} y={n.y} width={n.w} height={n.h} rx="6"
              fill={n.color + "33"} stroke={n.color} strokeWidth="1.5" />
            <text x={n.x + n.w / 2} y={n.y + n.h / 2 + 4}
              textAnchor="middle" fontSize="9" fill="#d1d5db" fontFamily="monospace">
              {n.label}
            </text>
          </g>
        ))}
      </svg>
    </div>
  );
}

function SlotCard({ slot, onSave }: { slot: ModelSlot; onSave: (patch: Partial<ModelSlot>) => void }) {
  const [editing, setEditing] = useState(false);
  const [provider, setProvider] = useState<ModelProvider>(slot.provider);
  const [model, setModel] = useState(slot.model);
  const [enabled, setEnabled] = useState(slot.enabled);
  const Icon = GROUP_ICONS[slot.group] || Cpu;

  function handleSave() {
    onSave({ provider, model, enabled });
    setEditing(false);
  }

  function handleCancel() {
    setProvider(slot.provider);
    setModel(slot.model);
    setEnabled(slot.enabled);
    setEditing(false);
  }

  return (
    <div
      data-testid={`model-slot-card-${slot.key}`}
      className={`rounded-lg border bg-card p-3 flex flex-col gap-2 transition-all ${!slot.enabled ? "opacity-50" : ""}`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <Icon className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
          <span className="text-xs font-semibold truncate">{slot.label}</span>
          <span className={`text-[10px] px-1.5 py-0.5 rounded border font-mono ${PROVIDER_COLORS[slot.provider]}`}>
            {slot.provider}
          </span>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          {editing ? (
            <>
              <button onClick={handleSave} data-testid={`save-slot-${slot.key}`}
                className="p-1 rounded hover:bg-muted text-green-400"><Check className="w-3 h-3" /></button>
              <button onClick={handleCancel} data-testid={`cancel-slot-${slot.key}`}
                className="p-1 rounded hover:bg-muted text-red-400"><X className="w-3 h-3" /></button>
            </>
          ) : (
            <button onClick={() => setEditing(true)} data-testid={`edit-slot-${slot.key}`}
              className="p-1 rounded hover:bg-muted text-muted-foreground"><Pencil className="w-3 h-3" /></button>
          )}
        </div>
      </div>

      <p className="text-[10px] text-muted-foreground leading-tight">{slot.description}</p>

      {editing ? (
        <div className="flex flex-col gap-2 pt-1 border-t border-border/50">
          <div className="flex items-center gap-2">
            <span className="text-[10px] text-muted-foreground w-14 shrink-0">Provider</span>
            <Select value={provider} onValueChange={v => { setProvider(v as ModelProvider); setModel(PROVIDER_MODELS[v as ModelProvider][0]); }}>
              <SelectTrigger className="h-6 text-xs" data-testid={`provider-select-${slot.key}`}>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="pcna">PCNA (native)</SelectItem>
                <SelectItem value="gemini">Gemini</SelectItem>
                <SelectItem value="xai">xAI / Grok</SelectItem>
                <SelectItem value="ollama">Ollama (local)</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] text-muted-foreground w-14 shrink-0">Model</span>
            {PROVIDER_MODELS[provider].length > 1 ? (
              <Select value={model} onValueChange={setModel}>
                <SelectTrigger className="h-6 text-xs" data-testid={`model-select-${slot.key}`}>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {PROVIDER_MODELS[provider].map(m => <SelectItem key={m} value={m}>{m}</SelectItem>)}
                </SelectContent>
              </Select>
            ) : (
              <Input value={model} onChange={e => setModel(e.target.value)}
                className="h-6 text-xs font-mono" data-testid={`model-input-${slot.key}`} />
            )}
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] text-muted-foreground w-14 shrink-0">Enabled</span>
            <Switch checked={enabled} onCheckedChange={setEnabled} data-testid={`enabled-switch-${slot.key}`}
              className="h-4 w-7" />
          </div>
        </div>
      ) : (
        <div className="flex items-center gap-2 font-mono text-[10px] text-muted-foreground">
          <ChevronRight className="w-3 h-3 shrink-0" />
          <span className="truncate">{slot.model}</span>
          {!slot.enabled && <Badge variant="outline" className="text-[9px] py-0 px-1 ml-auto">disabled</Badge>}
        </div>
      )}
    </div>
  );
}

export function ModelFlowTab() {
  const { toast } = useToast();

  const { data: slots = [], isLoading } = useQuery<ModelSlot[]>({
    queryKey: ["/api/model-slots"],
  });

  const mutation = useMutation({
    mutationFn: ({ key, patch }: { key: string; patch: Partial<ModelSlot> }) =>
      apiRequest("PUT", `/api/model-slots/${encodeURIComponent(key)}`, patch),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/model-slots"] });
      toast({ title: "Slot updated", description: "Change takes effect on next heartbeat tick." });
    },
    onError: (e: any) => toast({ title: "Save failed", description: e.message, variant: "destructive" }),
  });

  const groups = Array.from(new Set(slots.map(s => s.group)));

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div className="px-4 pt-4 pb-2 border-b border-border/50 shrink-0">
        <h2 className="text-sm font-semibold">Model Information Flow</h2>
        <p className="text-[11px] text-muted-foreground mt-0.5">
          Every model call routes through a named slot. Change the slot here and the change propagates everywhere that slot is used.
        </p>
      </div>

      <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-5">
        <div className="rounded-lg border border-border/50 bg-muted/30 p-3">
          <p className="text-[10px] text-muted-foreground mb-2 uppercase tracking-wider font-semibold">Information Flow</p>
          <FlowDiagram />
        </div>

        {isLoading ? (
          <div className="text-xs text-muted-foreground text-center py-8">Loading slots…</div>
        ) : (
          groups.map(group => (
            <div key={group}>
              <div className="flex items-center gap-2 mb-2">
                {GROUP_ICONS[group] && (() => { const I = GROUP_ICONS[group]; return <I className="w-3.5 h-3.5 text-muted-foreground" />; })()}
                <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">{group}</span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {slots.filter(s => s.group === group).map(slot => (
                  <SlotCard
                    key={slot.key}
                    slot={slot}
                    onSave={patch => mutation.mutate({ key: slot.key, patch })}
                  />
                ))}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
