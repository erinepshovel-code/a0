import { useQuery, useMutation } from "@tanstack/react-query";
import { apiRequest, queryClient } from "@/lib/queryClient";

export type Persona = "free" | "legal" | "researcher" | "political";

export function usePersona() {
  const { data, isLoading } = useQuery<{ persona: Persona }>({
    queryKey: ["/api/user/persona"],
  });

  const mutation = useMutation({
    mutationFn: (p: Persona) => apiRequest("PATCH", "/api/user/persona", { persona: p }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["/api/user/persona"] }),
  });

  return {
    persona: data?.persona ?? "free",
    isLoading,
    setPersona: (p: Persona) => mutation.mutate(p),
    isPending: mutation.isPending,
  };
}
