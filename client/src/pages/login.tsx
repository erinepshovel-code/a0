import { Shield, Key, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/hooks/use-auth";
import { useLocation } from "wouter";
import { useSEO } from "@/hooks/use-seo";
import { useEffect, useState } from "react";
import { useToast } from "@/hooks/use-toast";
import { queryClient } from "@/lib/queryClient";

export default function LoginPage() {
  useSEO({ title: "Sign In — a0p", description: "Sign in to a0p." });
  const { isAuthenticated, isLoading } = useAuth();
  const [, setLocation] = useLocation();
  const { toast } = useToast();
  const [key, setKey] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (isAuthenticated) {
      setLocation("/");
    }
  }, [isAuthenticated, setLocation]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!key.trim()) return;
    setSubmitting(true);
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ key: key.trim() }),
      });
      if (res.ok) {
        await queryClient.invalidateQueries({ queryKey: ["/api/auth/user"] });
        setLocation("/");
      } else {
        toast({ title: "Invalid key", description: "Check your access key and try again.", variant: "destructive" });
        setKey("");
      }
    } catch {
      toast({ title: "Error", description: "Could not connect. Try again.", variant: "destructive" });
    } finally {
      setSubmitting(false);
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-black flex items-center justify-center">
        <div className="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div
      className="min-h-screen bg-black text-white flex flex-col"
      data-testid="login-page"
    >
      <div className="flex-1 flex flex-col items-center justify-center px-6 py-12 max-w-sm mx-auto w-full">
        <div className="text-center space-y-10 w-full">
          <div className="space-y-3">
            <h1
              className="text-5xl font-black tracking-tighter"
              data-testid="text-login-title"
            >
              Agent Zero
            </h1>
            <div className="flex items-center justify-center gap-2">
              <Shield className="w-3.5 h-3.5 text-primary" />
              <span className="text-xs text-zinc-500 uppercase tracking-widest font-medium">
                Access required
              </span>
            </div>
          </div>

          <form onSubmit={handleSubmit} className="space-y-3 w-full">
            <div className="relative">
              <Key className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
              <Input
                type="text"
                placeholder="XXXX-XXXX access key"
                value={key}
                onChange={(e) => setKey(e.target.value)}
                className="pl-10 bg-zinc-900 border-zinc-700 text-white placeholder:text-zinc-600 font-mono tracking-widest text-center uppercase"
                data-testid="input-access-key"
                autoFocus
                autoComplete="off"
                spellCheck={false}
              />
            </div>
            <Button
              type="submit"
              size="lg"
              className="w-full"
              disabled={submitting || !key.trim()}
              data-testid="button-sign-in"
            >
              {submitting ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                "Enter"
              )}
            </Button>
          </form>

          <p className="text-[11px] text-zinc-600 leading-relaxed">
            Find your access key in the server logs.
            <br />
            Look for: <span className="font-mono text-zinc-500">[auth] Access key: XXXX-XXXX</span>
          </p>
        </div>
      </div>

      <div className="text-center pb-6 px-4">
        <p className="text-[10px] text-zinc-700">
          a0p v1.1.0-M1 · TIW Canon · EDCMBONE
        </p>
      </div>
    </div>
  );
}
