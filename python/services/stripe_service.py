import os
import stripe
from sqlalchemy import select, text
from ..database import engine

STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")

PRODUCTS = [
    {
        "name": "Free",
        "product_key": "free",
        "lookup_key": "tier_free",
        "amount": 0,
        "interval": None,
        "currency": "usd",
        "description": "Free tier — access to a0 base features",
    },
    {
        "name": "Seeker Monthly",
        "product_key": "seeker_monthly",
        "lookup_key": "tier_seeker_monthly",
        "amount": 1200,
        "interval": "month",
        "currency": "usd",
        "description": "Seeker tier — $12/mo, expanded context and tools",
    },
    {
        "name": "Operator Monthly",
        "product_key": "operator_monthly",
        "lookup_key": "tier_operator_monthly",
        "amount": 3900,
        "interval": "month",
        "currency": "usd",
        "description": "Operator tier — $39/mo, full platform access",
    },
    {
        "name": "Way Seer Patron Monthly",
        "product_key": "patron_monthly",
        "lookup_key": "tier_patron_monthly",
        "amount": 5300,
        "interval": "month",
        "currency": "usd",
        "description": "Way Seer Patron — $53/mo, patron-level access",
    },
    {
        "name": "Founder Lifetime",
        "product_key": "founder_lifetime",
        "lookup_key": "tier_founder_lifetime",
        "amount": 53000,
        "interval": None,
        "currency": "usd",
        "description": "Founder Lifetime — one-time $530, first 53 slots",
    },
    {
        "name": "BYOK Add-On Monthly",
        "product_key": "byok_addon",
        "lookup_key": "addon_byok_monthly",
        "amount": 900,
        "interval": "month",
        "currency": "usd",
        "description": "Bring Your Own Key add-on — $9/mo",
    },
    {
        "name": "Credit Pack 100",
        "product_key": "credits_100",
        "lookup_key": "credits_100",
        "amount": 800,
        "interval": None,
        "currency": "usd",
        "description": "100 AI credits — $8 one-time",
    },
    {
        "name": "Credit Pack 300",
        "product_key": "credits_300",
        "lookup_key": "credits_300",
        "amount": 2000,
        "interval": None,
        "currency": "usd",
        "description": "300 AI credits — $20 one-time",
    },
    {
        "name": "Credit Pack 1000",
        "product_key": "credits_1000",
        "lookup_key": "credits_1000",
        "amount": 6000,
        "interval": None,
        "currency": "usd",
        "description": "1000 AI credits — $60 one-time",
    },
]

# Module-level price ID cache populated on startup
PRICE_ID_CACHE: dict[str, str] = {}


async def ensure_stripe_products() -> list[dict]:
    if not STRIPE_SECRET_KEY:
        print("[stripe] STRIPE_SECRET_KEY not set — skipping product bootstrap")
        return []

    stripe.api_key = STRIPE_SECRET_KEY
    results = []
    for spec in PRODUCTS:
        if spec["amount"] == 0:
            continue
        try:
            existing = stripe.Price.list(lookup_keys=[spec["lookup_key"]], limit=1)
            if existing.data:
                price_id = existing.data[0].id
                PRICE_ID_CACHE[spec["product_key"]] = price_id
                results.append({"lookup_key": spec["lookup_key"], "status": "exists", "price_id": price_id})
                continue

            product = stripe.Product.create(
                name=spec["name"],
                description=spec["description"],
            )
            price_kwargs: dict = {
                "unit_amount": spec["amount"],
                "currency": spec["currency"],
                "product": product.id,
                "lookup_key": spec["lookup_key"],
                "transfer_lookup_key": True,
            }
            if spec["interval"]:
                price_kwargs["recurring"] = {"interval": spec["interval"]}
            price = stripe.Price.create(**price_kwargs)
            PRICE_ID_CACHE[spec["product_key"]] = price.id
            results.append({"lookup_key": spec["lookup_key"], "status": "created", "price_id": price.id})
        except Exception as exc:
            results.append({"lookup_key": spec["lookup_key"], "status": "error", "error": str(exc)})

    ok = sum(1 for r in results if r["status"] in ("created", "exists"))
    print(f"[stripe] Products ensured: {ok}/{len(PRODUCTS) - 1}")
    return results


def get_tier_context_name(tier: str) -> str:
    mapping = {
        "free": "tier_free",
        "seeker": "tier_seeker",
        "operator": "tier_operator",
        "patron": "tier_patron",
        "founder": "tier_founder",
    }
    return mapping.get(tier, "tier_free")
