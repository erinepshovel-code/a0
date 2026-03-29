import { storage } from "./storage";

export type ModelProvider = "pcna" | "gemini" | "xai" | "ollama";

export interface ModelSlot {
  key: string;
  label: string;
  group: string;
  description: string;
  provider: ModelProvider;
  model: string;
  enabled: boolean;
}

const DEFAULTS: ModelSlot[] = [
  {
    key: "heartbeat.goal_pursuit",
    label: "Goal Pursuit",
    group: "Heartbeat",
    description: "Assesses search results and plans next steps toward active goals",
    provider: "pcna",
    model: "native",
    enabled: true,
  },
  {
    key: "heartbeat.scheduled_tasks",
    label: "Scheduled Tasks",
    group: "Heartbeat",
    description: "Executes autonomous scheduled background tasks (research, memory, etc.)",
    provider: "pcna",
    model: "native",
    enabled: true,
  },
  {
    key: "chat.slot_a",
    label: "Chat Slot A",
    group: "Chat",
    description: "Primary chat model slot — main conversational responses",
    provider: "gemini",
    model: "gemini-2.5-flash-preview-04-17",
    enabled: true,
  },
  {
    key: "chat.slot_b",
    label: "Chat Slot B",
    group: "Chat",
    description: "Secondary chat model slot — alternative reasoning voice",
    provider: "xai",
    model: "grok-3-mini",
    enabled: true,
  },
  {
    key: "chat.slot_c",
    label: "Chat Slot C",
    group: "Chat",
    description: "Tertiary chat model slot — synthesis or specialist tasks",
    provider: "pcna",
    model: "native",
    enabled: false,
  },
  {
    key: "synthesis.merge",
    label: "Response Merge",
    group: "Synthesis",
    description: "Merges multiple slot responses into a single coherent reply",
    provider: "gemini",
    model: "gemini-2.5-flash-preview-04-17",
    enabled: true,
  },
  {
    key: "synthesis.assess",
    label: "Goal Assessment",
    group: "Synthesis",
    description: "Scores relevance of search results against active goals",
    provider: "pcna",
    model: "native",
    enabled: true,
  },
];

const REGISTRY_KEY = "model_registry_v1";

let _cache: ModelSlot[] | null = null;

export async function loadRegistry(): Promise<ModelSlot[]> {
  if (_cache) return _cache;
  try {
    const toggle = await storage.getSystemToggle(REGISTRY_KEY);
    if (toggle?.parameters) {
      const stored: Partial<ModelSlot>[] = Array.isArray(toggle.parameters)
        ? toggle.parameters
        : JSON.parse(String(toggle.parameters));
      _cache = DEFAULTS.map(def => {
        const override = stored.find((s: any) => s.key === def.key);
        return override ? { ...def, ...override } : def;
      });
      for (const s of stored) {
        if (_cache && !_cache.find(c => c.key === s.key) && s.key && s.label) {
          _cache.push({ ...DEFAULTS[0], ...s } as ModelSlot);
        }
      }
      return _cache!;
    }
  } catch {}
  _cache = [...DEFAULTS];
  return _cache;
}

export async function getSlot(key: string): Promise<ModelSlot> {
  const registry = await loadRegistry();
  return registry.find(s => s.key === key) ?? { ...DEFAULTS[0], key };
}

export async function updateSlot(key: string, patch: Partial<ModelSlot>): Promise<ModelSlot[]> {
  const registry = await loadRegistry();
  const idx = registry.findIndex(s => s.key === key);
  if (idx >= 0) {
    registry[idx] = { ...registry[idx], ...patch, key };
  } else {
    registry.push({ ...DEFAULTS[0], ...patch, key } as ModelSlot);
  }
  _cache = registry;
  await storage.upsertSystemToggle(REGISTRY_KEY, true, registry);
  return registry;
}

export async function listSlots(): Promise<ModelSlot[]> {
  return loadRegistry();
}

export function invalidateCache() {
  _cache = null;
}
