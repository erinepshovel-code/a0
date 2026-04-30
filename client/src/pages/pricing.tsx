// 213:0
import { useState, useCallback, useEffect } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { loadStripe } from "@stripe/stripe-js";
import { EmbeddedCheckout, EmbeddedCheckoutProvider } from "@stripe/react-stripe-js";
import { apiRequest } from "@/lib/queryClient";
import { useBillingStatus } from "@/hooks/use-billing-status";
import { useSEO } from "@/hooks/use-seo";
import { useToast } from "@/hooks/use-toast";
import { Loader2, Check, X, Heart, Wrench } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";

interface BillingConfig {
  stripe_publishable_key: string;
  donation_min_cents: number;
}

interface FundingStatement {
  statement: string;
}

function formatAmount(cents: number): string {
  return `$${(cents / 100).toFixed(2)}`;
}

const FUNDING_FALLBACK =
  "I don't have the cash required for 501c3 status, so I have to report it for taxes, " +
  "but every tax payer is allowed to claim up to five hundred dollars in charitable " +
  "donations per year without receipts required.";

export default function PricingPage() {
  useSEO({
    title: "Donate — a0p",
    description:
      "a0p is a research instrument, not a product. Every tab is free for everyone. " +
      "Donations fund the instrument; they do not unlock features.",
  });
  const { tier, isAdmin, isWs } = useBillingStatus();
  const { toast } = useToast();

  const [donateDollars, setDonateDollars] = useState("5");
  const [checkoutOpen, setCheckoutOpen] = useState(false);
  const [clientSecret, setClientSecret] = useState<string | null>(null);
  const [stripePromise, setStripePromise] = useState<ReturnType<typeof loadStripe> | null>(null);

  const { data: config } = useQuery<BillingConfig>({
    queryKey: ["/api/v1/billing/config"],
    staleTime: Infinity,
  });

  const { data: funding } = useQuery<FundingStatement>({
    queryKey: ["/api/v1/billing/funding-statement"],
    staleTime: Infinity,
  });

  const minCents = config?.donation_min_cents ?? 500;
  const donateCents = Math.round(parseFloat(donateDollars || "0") * 100);
  const isValidAmount = donateCents >= minCents;

  // If a previously-active recurring subscription is still in flight (a
  // grandfathered Supporter sub from before the donations-only reframe), the
  // user can still self-cancel via Stripe customer portal.
  const portalMutation = useMutation({
    mutationFn: async () => {
      const res = await apiRequest("POST", "/api/v1/billing/portal", {
        return_url: `${window.location.origin}/pricing`,
      });
      return res.json();
    },
    onSuccess: (data) => {
      window.location.href = data.url;
    },
    onError: (err: Error) => {
      toast({ title: "Portal error", description: err.message, variant: "destructive" });
    },
  });

  const donateMutation = useMutation({
    mutationFn: async () => {
      const res = await apiRequest("POST", "/api/v1/billing/donate", {
        amount_cents: donateCents,
        return_url: `${window.location.origin}/pricing?donation=success`,
      });
      return res.json();
    },
    onSuccess: (data) => {
      if (!config?.stripe_publishable_key) {
        toast({ title: "Stripe not configured", variant: "destructive" });
        return;
      }
      setStripePromise(loadStripe(config.stripe_publishable_key));
      setClientSecret(data.client_secret);
      setCheckoutOpen(true);
    },
    onError: (err: Error) => {
      toast({ title: "Donation error", description: err.message, variant: "destructive" });
    },
  });

  const fetchClientSecret = useCallback(() => Promise.resolve(clientSecret!), [clientSecret]);

  // If the user lands here from a successful donation return URL, show a thanks toast.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("donation") === "success") {
      toast({
        title: "Thank you",
        description: "Your donation funds the instrument. Nothing about your access changed — every tab was already yours.",
      });
    }
  }, [toast]);

  const isGrandfatheredSupporter = tier === "supporter";

  return (
    <div className="min-h-screen bg-background pb-20 px-4 pt-6 max-w-lg mx-auto">
      <div className="mb-8 text-center">
        <div className="flex justify-center mb-3">
          <Wrench className="w-6 h-6 text-primary" />
        </div>
        <h1 className="text-2xl font-bold text-foreground mb-2">a0p is a research instrument</h1>
        <p className="text-sm text-muted-foreground max-w-md mx-auto">
          Not a product. Every tab is free for everyone. Donations fund the instrument; they do not unlock features.
        </p>
      </div>

      <div className="space-y-4">
        <div
          className="rounded-xl border border-border bg-card p-5"
          data-testid="plan-card-free"
        >
          <div className="flex items-start justify-between mb-3">
            <div>
              <h3 className="font-semibold text-foreground">Open access</h3>
              <p className="text-xs text-muted-foreground mt-0.5">Full console — every tab unlocked, no payment required</p>
            </div>
            <span className="text-lg font-bold text-foreground">$0</span>
          </div>
          <ul className="space-y-1.5">
            {[
              "Full console — every tab unlocked",
              "ZFAE agent with EDCM awareness",
              "PCNA alignment engine active",
              "Bandit model routing on the PCNA core",
            ].map((f) => (
              <li key={f} className="flex items-start gap-2 text-sm text-muted-foreground">
                <Check className="w-3.5 h-3.5 mt-0.5 shrink-0 text-primary" />
                <span>{f}</span>
              </li>
            ))}
          </ul>
          {tier === "free" && !isAdmin && (
            <div className="mt-3">
              <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-muted text-muted-foreground" data-testid="badge-current-plan">
                That's you
              </span>
            </div>
          )}
        </div>

        <div
          className="rounded-xl border border-border bg-card p-5"
          data-testid="plan-card-donate"
        >
          <div className="flex items-start justify-between mb-1">
            <div className="flex items-center gap-2">
              <Heart className="w-4 h-4 text-primary" />
              <h3 className="font-semibold text-foreground">Donate</h3>
            </div>
          </div>
          <p className="text-sm text-muted-foreground mb-3" data-testid="text-donation-purpose">
            One-off donation in any amount you choose. Funds the instrument.
            Does not change your access — everything was already free.
          </p>

          <div
            className="rounded-lg border border-border bg-background p-3 mb-4 text-xs text-muted-foreground leading-relaxed"
            data-testid="text-funding-statement"
          >
            {funding?.statement || FUNDING_FALLBACK}
          </div>

          <div className="mb-3">
            <label className="text-xs font-medium text-muted-foreground mb-1 block">
              Donation amount
            </label>
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">$</span>
              <input
                type="number"
                min={minCents / 100}
                step="1"
                value={donateDollars}
                onChange={(e) => setDonateDollars(e.target.value)}
                className="flex-1 bg-background border border-border rounded-md px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                placeholder="5"
                data-testid="input-donate-amount"
              />
              <span className="text-xs text-muted-foreground">USD</span>
            </div>
            {donateCents > 0 && donateCents < minCents && (
              <p className="text-xs text-destructive mt-1" data-testid="text-min-error">
                Minimum donation is {formatAmount(minCents)}
              </p>
            )}
          </div>

          <Button
            className="w-full"
            onClick={() => donateMutation.mutate()}
            disabled={!isValidAmount || donateMutation.isPending}
            data-testid="btn-donate"
          >
            {donateMutation.isPending ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              `Donate ${formatAmount(Math.max(donateCents, minCents))}`
            )}
          </Button>
        </div>

        {isGrandfatheredSupporter && (
          <div
            className="rounded-xl border border-amber-500/30 bg-amber-500/5 p-5"
            data-testid="plan-card-grandfathered-supporter"
          >
            <div className="flex items-start justify-between mb-2">
              <h3 className="font-semibold text-foreground">Active recurring subscription</h3>
              <span className="text-xs font-medium px-2 py-0.5 rounded-full border border-amber-500/40 text-amber-400">
                Grandfathered
              </span>
            </div>
            <p className="text-sm text-muted-foreground mb-3">
              You signed up for a Supporter subscription before the reframe to donations-only. The subscription still
              works, but new users no longer see this option. You can self-cancel anytime via the Stripe portal.
            </p>
            <Button
              size="sm"
              variant="outline"
              onClick={() => portalMutation.mutate()}
              disabled={portalMutation.isPending}
              className="w-full"
              data-testid="btn-manage-subscription"
            >
              {portalMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : "Manage subscription"}
            </Button>
          </div>
        )}

        {(isWs || isAdmin) && !isGrandfatheredSupporter && (
          <div className="rounded-xl border border-violet-500/30 bg-violet-500/5 p-5" data-testid="plan-card-ws">
            <div className="flex items-start justify-between mb-2">
              <h3 className="font-semibold text-foreground">Owner / WS access</h3>
              <span className="text-xs font-medium px-2 py-0.5 rounded-full border border-violet-500/40 text-violet-400">
                {isAdmin ? "Owner" : "WS"}
              </span>
            </div>
            <p className="text-sm text-muted-foreground">
              {isAdmin
                ? "You have owner access — write actions that alter the instrument's code, configuration, or shared learning state are gated to you."
                : "Granted to @interdependentway.org accounts — full ws-tier access."}
            </p>
          </div>
        )}
      </div>

      <div className="mt-10 text-center">
        <p className="text-xs text-muted-foreground max-w-sm mx-auto">
          a0p exists to be researched and to research itself. Use it freely; donate if it earns its keep.
        </p>
      </div>

      <Dialog open={checkoutOpen} onOpenChange={(open) => { if (!open) setCheckoutOpen(false); }}>
        <DialogContent className="max-w-lg p-0 gap-0 overflow-hidden" data-testid="checkout-dialog">
          <DialogHeader className="px-4 pt-4 pb-2 border-b border-border">
            <div className="flex items-center justify-between">
              <DialogTitle className="text-sm font-medium">Complete your donation</DialogTitle>
              <button
                onClick={() => setCheckoutOpen(false)}
                className="text-muted-foreground hover:text-foreground"
                data-testid="btn-close-checkout"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </DialogHeader>
          <div className="min-h-[400px]">
            {stripePromise && clientSecret && (
              <EmbeddedCheckoutProvider stripe={stripePromise} options={{ fetchClientSecret }}>
                <EmbeddedCheckout />
              </EmbeddedCheckoutProvider>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
// 213:0
