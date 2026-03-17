import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "@/lib/queryClient";

export type Persona = "free" | "legal" | "researcher" | "political";

export const PERSONA_LABELS: Record<Persona, string> = {
  free: "Free",
  legal: "Legal",
  researcher: "Researcher",
  political: "Political",
};

export const PERSONA_DESCRIPTIONS: Record<Persona, string> = {
  free: "General-purpose AI agent for everyday tasks, automation, and coding.",
  legal: "Compliance-focused lens. EDCM metrics frame legal risk, regulatory gaps, and liability exposure.",
  researcher: "Empirical rigor mode. EDCM tracks concept drift, data accuracy, and interpretability.",
  political: "Electoral strategy lens. EDCM maps to campaign momentum, narrative drift, and demographic alignment.",
};

export const PERSONA_ICONS: Record<Persona, string> = {
  free: "⚡",
  legal: "⚖",
  researcher: "🔬",
  political: "🗳",
};

export function usePersona() {
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery<{ persona: Persona }>({
    queryKey: ["/api/user/persona"],
  });

  const mutation = useMutation({
    mutationFn: (persona: Persona) =>
      apiRequest("PATCH", "/api/user/persona", { persona }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/user/persona"] });
    },
  });

  return {
    persona: data?.persona ?? "free",
    isLoading,
    setPersona: (p: Persona) => mutation.mutate(p),
    isPending: mutation.isPending,
  };
}
