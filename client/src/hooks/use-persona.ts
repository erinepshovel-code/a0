import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "@/lib/queryClient";

export type Persona = "free" | "legal" | "researcher" | "political" | "founder";

const LS_KEY = "a0p-persona";

export const PERSONA_META: Record<Persona, { label: string; description: string; icon: string }> = {
  free: {
    label: "Free",
    description: "Basic transcript upload and EDCM analysis. A0 explains results in plain language.",
    icon: "📄",
  },
  legal: {
    label: "Legal Professional",
    description: "Deposition, court transcript and witness analysis. Metrics framed in legal terms. A0 acts as a paralegal analyst.",
    icon: "⚖️",
  },
  researcher: {
    label: "AI Researcher",
    description: "Full technical console — tensor internals, PTCA triad, PCNA nodes, heartbeat cycles, model registry.",
    icon: "🔬",
  },
  political: {
    label: "Political / Analyst",
    description: "Speech, debate and interview analysis. Message discipline, narrative consistency, frame breaks. A0 as discourse analyst.",
    icon: "🗣️",
  },
  founder: {
    label: "Founder",
    description: "Full access across all views. Backs the whole project.",
    icon: "🌱",
  },
};

function readLocal(): Persona {
  try {
    const v = localStorage.getItem(LS_KEY) as Persona | null;
    if (v && ["free", "legal", "researcher", "political", "founder"].includes(v)) return v;
  } catch {}
  return "free";
}

function writeLocal(p: Persona) {
  try { localStorage.setItem(LS_KEY, p); } catch {}
}

export function usePersona() {
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery<{ persona: Persona }>({
    queryKey: ["/api/user/persona"],
    staleTime: 30_000,
  });

  const mutation = useMutation({
    mutationFn: async (persona: Persona) => {
      writeLocal(persona);
      return apiRequest("PATCH", "/api/user/persona", { persona });
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["/api/user/persona"] }),
  });

  const serverPersona = data?.persona;
  const localPersona = readLocal();
  const persona: Persona = serverPersona ?? localPersona;

  return {
    persona,
    setPersona: (p: Persona) => {
      writeLocal(p);
      queryClient.setQueryData(["/api/user/persona"], { persona: p });
      mutation.mutate(p);
    },
    isLoading,
    isPending: mutation.isPending,
  };
}
