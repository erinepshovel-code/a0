import { useState, useEffect } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { apiRequest, queryClient } from "@/lib/queryClient";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/hooks/use-toast";
import { Check, ChevronDown, ChevronRight, Lock, Pencil } from "lucide-react";
import { cn } from "@/lib/utils";

type Section = { label: string; key: string; editable: boolean; content: string };
type FullPreview = { sections: Section[]; persona: string };

function SectionBlock({ section, value, onChange }: {
  section: Section;
  value?: string;
  onChange?: (v: string) => void;
}) {
  const [open, setOpen] = useState(section.editable);
  const content = section.editable ? (value ?? section.content) : section.content;

  return (
    <div className={cn("rounded-lg border bg-card overflow-hidden", section.editable ? "border-primary/30" : "border-border")}>
      <button
        className="w-full flex items-center gap-2 px-3 py-2.5 text-left hover:bg-accent/50 transition-colors"
        onClick={() => setOpen(o => !o)}
        data-testid={`button-section-${section.key}`}
      >
        {open ? <ChevronDown className="w-3.5 h-3.5 text-muted-foreground flex-shrink-0" /> : <ChevronRight className="w-3.5 h-3.5 text-muted-foreground flex-shrink-0" />}
        <span className="text-xs font-semibold flex-1">{section.label}</span>
        {section.editable
          ? <Badge variant="outline" className="text-[9px] border-primary/50 text-primary gap-0.5"><Pencil className="w-2.5 h-2.5" />editable</Badge>
          : <Badge variant="outline" className="text-[9px] gap-0.5 text-muted-foreground"><Lock className="w-2.5 h-2.5" />system</Badge>
        }
      </button>
      {open && (
        <div className="px-3 pb-3">
          {section.editable && onChange ? (
            <Textarea
              value={content}
              onChange={e => onChange(e.target.value)}
              className="min-h-[90px] font-mono text-[10px] resize-none bg-background"
              data-testid={`textarea-${section.key}`}
            />
          ) : (
            <pre className="font-mono text-[10px] text-muted-foreground whitespace-pre-wrap leading-relaxed bg-background rounded p-2 max-h-48 overflow-auto"
              data-testid={`text-section-${section.key}`}>
              {content}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}

export function ContextTab() {
  const { toast } = useToast();
  const [view, setView] = useState<"sections" | "raw">("sections");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [contextPrefix, setContextPrefix] = useState("");
  const [loaded, setLoaded] = useState(false);

  const { data: preview, isLoading } = useQuery<FullPreview>({
    queryKey: ["/api/v1/context/full-preview"],
    staleTime: 30000,
  });

  useEffect(() => {
    if (preview && !loaded) {
      const sp = preview.sections.find(s => s.key === "systemPrompt");
      const cp = preview.sections.find(s => s.key === "contextPrefix");
      if (sp) setSystemPrompt(sp.content);
      if (cp) setContextPrefix(cp.content);
      setLoaded(true);
    }
  }, [preview, loaded]);

  const saveMutation = useMutation({
    mutationFn: () => apiRequest("POST", "/api/context", { systemPrompt, contextPrefix }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/v1/context/full-preview"] });
      queryClient.invalidateQueries({ queryKey: ["/api/v1/context"] });
      toast({ title: "Context saved and active" });
    },
    onError: (e: any) => toast({ title: "Error", description: e.message, variant: "destructive" }),
  });

  const editableValues: Record<string, string> = { systemPrompt, contextPrefix };
  const editableSetters: Record<string, (v: string) => void> = {
    systemPrompt: setSystemPrompt,
    contextPrefix: setContextPrefix,
  };

  const rawAssembled = preview?.sections.map(s => {
    const val = s.editable ? editableValues[s.key] : s.content;
    return `# ${s.label.toUpperCase()}${s.editable ? " [editable]" : " [system]"}\n${val}`;
  }).join("\n\n---\n\n") ?? "";

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-1 px-3 pt-3 pb-2 flex-shrink-0">
        <button
          onClick={() => setView("sections")}
          className={cn("px-3 py-1 rounded-full text-[11px] font-medium transition-colors", view === "sections" ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground")}
          data-testid="button-view-sections"
        >Sections</button>
        <button
          onClick={() => setView("raw")}
          className={cn("px-3 py-1 rounded-full text-[11px] font-medium transition-colors", view === "raw" ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground")}
          data-testid="button-view-raw"
        >Full Prompt</button>
        {preview && (
          <Badge variant="outline" className="ml-auto text-[9px]">persona: {preview.persona}</Badge>
        )}
      </div>

      <ScrollArea className="flex-1 px-3">
        <div className="space-y-2 pb-4">
          {isLoading && (
            <div className="text-xs text-muted-foreground text-center py-8">Loading prompt…</div>
          )}

          {view === "sections" && preview?.sections.map(section => (
            <SectionBlock
              key={section.key}
              section={section}
              value={section.editable ? editableValues[section.key] : undefined}
              onChange={section.editable ? editableSetters[section.key] : undefined}
            />
          ))}

          {view === "raw" && (
            <div className="rounded-lg border border-border bg-card p-3">
              <p className="text-[10px] text-muted-foreground mb-2">Full assembled prompt sent to a0 on each request. Editable sections reflect your current unsaved edits.</p>
              <pre className="font-mono text-[10px] text-muted-foreground whitespace-pre-wrap leading-relaxed bg-background rounded p-2 overflow-auto max-h-[60vh]" data-testid="text-full-prompt">
                {rawAssembled}
              </pre>
            </div>
          )}

          <Button
            className="w-full mt-2"
            onClick={() => saveMutation.mutate()}
            disabled={saveMutation.isPending}
            data-testid="button-save-context"
          >
            <Check className="w-4 h-4 mr-1" />
            {saveMutation.isPending ? "Saving…" : "Save Editable Sections"}
          </Button>
        </div>
      </ScrollArea>
    </div>
  );
}
