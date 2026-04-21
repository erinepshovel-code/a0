// N:M
import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Loader2, Activity, ChevronRight, ChevronDown, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useSEO } from "@/hooks/use-seo";
import { cn } from "@/lib/utils";

interface RunNode {
  id: string;
  parent_run_id: string | null;
  root_run_id: string | null;
  depth: number;
  status: "running" | "completed" | "failed" | "killed" | string;
  orchestration_mode: string;
  cut_mode: string;
  providers: string[];
  spawned_by_tool: string | null;
  task_summary: string;
  started_at: string | null;
  ended_at: string | null;
  duration_ms: number | null;
  total_tokens: number;
  total_cost_usd: number;
  children: RunNode[];
}

interface TreeRes {
  roots: RunNode[];
  stats: {
    total_runs: number;
    active_count: number;
    cost_today_usd: number;
    depth_histogram: Record<string, number>;
  };
}

interface LogEntry {
  id: number;
  run_id: string;
  depth: number;
  level: string;
  event: string;
  payload: unknown;
  ts: string | null;
}

const STATUS_COLOR: Record<string, string> = {
  running: "bg-amber-500/15 text-amber-500 border-amber-500/30",
  completed: "bg-emerald-500/15 text-emerald-500 border-emerald-500/30",
  failed: "bg-destructive/15 text-destructive border-destructive/30",
  killed: "bg-muted text-muted-foreground border-border",
};

function fmtDur(ms: number | null): string {
  if (ms == null) return "—";
  if (ms < 1000) return `${ms}ms`;
  const s = ms / 1000;
  if (s < 60) return `${s.toFixed(1)}s`;
  const m = Math.floor(s / 60);
  return `${m}m ${Math.round(s - m * 60)}s`;
}

function RunRow({
  run,
  selectedId,
  onSelect,
}: {
  run: RunNode;
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  const [open, setOpen] = useState(true);
  const isSel = selectedId === run.id;
  const hasKids = run.children.length > 0;
  return (
    <div data-testid={`run-row-${run.id}`}>
      <button
        type="button"
        onClick={() => onSelect(run.id)}
        className={cn(
          "w-full flex items-center gap-2 px-2 py-1.5 text-left text-xs rounded-md hover-elevate",
          isSel && "bg-muted",
        )}
        style={{ paddingLeft: `${8 + run.depth * 16}px` }}
        data-testid={`btn-select-run-${run.id}`}
      >
        {hasKids ? (
          <span
            role="button"
            tabIndex={0}
            onClick={(e) => { e.stopPropagation(); setOpen((v) => !v); }}
            className="text-muted-foreground"
          >
            {open ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
          </span>
        ) : (
          <span className="w-3" />
        )}
        <Badge variant="outline" className={cn("text-[9px] h-4 px-1 capitalize", STATUS_COLOR[run.status] ?? "")}>
          {run.status}
        </Badge>
        <span className="font-mono text-[10px] text-muted-foreground">{run.id.slice(0, 8)}</span>
        <span className="flex-1 truncate">{run.task_summary || run.spawned_by_tool || "(unnamed)"}</span>
        <span className="text-[9px] text-muted-foreground hidden sm:inline">{run.orchestration_mode}</span>
        <span className="text-[9px] text-muted-foreground tabular-nums">{fmtDur(run.duration_ms)}</span>
        {run.total_cost_usd > 0 && (
          <span className="text-[9px] text-muted-foreground tabular-nums">${run.total_cost_usd.toFixed(4)}</span>
        )}
      </button>
      {hasKids && open && (
        <div>
          {run.children.map((c) => (
            <RunRow key={c.id} run={c} selectedId={selectedId} onSelect={onSelect} />
          ))}
        </div>
      )}
    </div>
  );
}

function LogTail({ runId }: { runId: string }) {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [connected, setConnected] = useState(false);
  const tailRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setLogs([]);
    setConnected(false);
    const es = new EventSource(`/api/v1/runs/${runId}/logs/stream`);
    let terminal = false;
    es.onopen = () => setConnected(true);
    es.onerror = () => {
      setConnected(false);
      // Stop reconnect churn once the backend has signaled a terminal state
      // (it closes the connection after emitting the terminal heartbeat).
      if (terminal) es.close();
    };
    es.addEventListener("log", (ev: MessageEvent) => {
      try {
        const data = JSON.parse(ev.data) as LogEntry;
        setLogs((prev) => [...prev.slice(-499), data]);
      } catch {
        /* ignore */
      }
    });
    es.addEventListener("heartbeat", (ev: MessageEvent) => {
      try {
        const hb = JSON.parse(ev.data) as { status?: string };
        if (hb.status && !["running", "queued", "pending"].includes(hb.status)) {
          terminal = true;
          es.close();
          setConnected(false);
        }
      } catch {
        /* ignore */
      }
    });
    return () => { es.close(); };
  }, [runId]);

  useEffect(() => {
    if (tailRef.current) tailRef.current.scrollTop = tailRef.current.scrollHeight;
  }, [logs]);

  return (
    <div className="flex-1 flex flex-col min-h-0" data-testid="log-tail">
      <div className="flex items-center gap-2 px-3 py-1.5 border-b border-border text-[10px] uppercase tracking-wider text-muted-foreground">
        <Activity className={cn("h-3 w-3", connected ? "text-emerald-500" : "text-muted-foreground")} />
        <span>{connected ? "live" : "disconnected"}</span>
        <span className="ml-auto font-mono text-[9px]">{runId.slice(0, 12)}</span>
      </div>
      <div ref={tailRef} className="flex-1 overflow-auto p-2 font-mono text-[10px] space-y-0.5">
        {logs.length === 0 ? (
          <p className="text-muted-foreground italic">waiting for events…</p>
        ) : logs.map((l) => (
          <div key={l.id ?? `${l.ts}-${l.event}`} className="flex gap-2" data-testid={`log-${l.id}`}>
            <span className="text-muted-foreground shrink-0">{l.ts?.slice(11, 19) ?? "—"}</span>
            <span className={cn(
              "shrink-0 uppercase w-10",
              l.level === "error" && "text-destructive",
              l.level === "warn" && "text-amber-500",
              l.level === "info" && "text-foreground/70",
              l.level === "debug" && "text-muted-foreground",
            )}>{l.level}</span>
            <span className="shrink-0 text-primary">{l.event}</span>
            <span className="text-muted-foreground truncate">
              {typeof l.payload === "string" ? l.payload : JSON.stringify(l.payload)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function FleetPage() {
  useSEO({ title: "a0p — Fleet", description: "Live view of agent runs, sub-agents, and recursion depth." });
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const { data, isLoading, error } = useQuery<TreeRes>({
    queryKey: ["/api/v1/runs/tree"],
    refetchInterval: 5_000,
  });

  useEffect(() => {
    if (!selectedId && data?.roots && data.roots.length > 0) {
      setSelectedId(data.roots[0].id);
    }
  }, [data, selectedId]);

  return (
    <div className="flex flex-col h-full" data-testid="fleet-page">
      <div className="flex items-center gap-3 px-4 py-2 border-b border-border bg-card">
        <h1 className="text-sm font-semibold">Fleet</h1>
        {data?.stats && (
          <>
            <Badge variant="outline" className="text-[10px]">{data.stats.total_runs} runs</Badge>
            <Badge variant="outline" className="text-[10px] text-amber-500 border-amber-500/30">
              {data.stats.active_count} active
            </Badge>
            <Badge variant="outline" className="text-[10px]">${data.stats.cost_today_usd.toFixed(4)}</Badge>
          </>
        )}
      </div>

      <div className="flex-1 flex min-h-0 flex-col md:flex-row">
        <div className="md:w-1/2 lg:w-2/5 border-b md:border-b-0 md:border-r border-border overflow-auto">
          {isLoading ? (
            <div className="p-6 flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" /> Loading runs…
            </div>
          ) : error ? (
            <div className="p-6 text-sm text-destructive" data-testid="fleet-error">
              Failed to load runs: {(error as Error).message}
            </div>
          ) : !data?.roots || data.roots.length === 0 ? (
            <div className="p-6 text-sm text-muted-foreground" data-testid="fleet-empty">
              No agent runs yet. Send a chat message to start one.
            </div>
          ) : (
            <div className="p-1">
              {data.roots.map((r) => (
                <RunRow key={r.id} run={r} selectedId={selectedId} onSelect={setSelectedId} />
              ))}
            </div>
          )}
        </div>

        <div className="flex-1 flex flex-col min-h-0">
          {selectedId ? (
            <>
              <div className="flex items-center px-3 py-1.5 border-b border-border">
                <span className="text-xs text-muted-foreground">Live log</span>
                <Button
                  size="icon"
                  variant="ghost"
                  className="ml-auto h-6 w-6"
                  onClick={() => setSelectedId(null)}
                  data-testid="btn-close-log"
                >
                  <X className="h-3 w-3" />
                </Button>
              </div>
              <LogTail runId={selectedId} />
            </>
          ) : (
            <div className="flex-1 flex items-center justify-center text-xs text-muted-foreground">
              Select a run to tail its logs
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
// N:M
