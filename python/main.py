import os
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, HTMLResponse

from .database import engine
from .engine import PCNAEngine
from .routes import ALL_ROUTERS, collect_ui_meta
from .services.heartbeat import heartbeat_service
from .agents.zfae import compose_name
from .services.energy_registry import energy_registry
from .auth import (
    ReplitAuthMiddleware,
    make_session_cookie,
    verify_access_key,
    get_access_key,
    SESSION_COOKIE,
)

_pcna: PCNAEngine | None = None
_instances: dict[str, PCNAEngine] = {}


def get_pcna() -> PCNAEngine:
    global _pcna
    if _pcna is None:
        _pcna = PCNAEngine()
        _instances[_pcna.guardian.instance_id] = _pcna
    return _pcna


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[python] FastAPI starting — DB engine initialized")
    pcna = get_pcna()
    print(f"[python] PCNA engine online — blueprint {pcna.blueprint_hash[:12]}...")
    await energy_registry.load_from_db()
    provider = energy_registry.get_active_provider()
    agent_name = compose_name(provider)
    print(f"[python] Agent: {agent_name}")
    from .routes.agents import ensure_primary_agent
    await ensure_primary_agent(pcna)
    print("[python] Primary agent verified, deprecated names cleaned")
    from .routes.contexts import _ensure_defaults as ensure_contexts
    await ensure_contexts()
    print("[python] Default prompt contexts ensured")
    from .routes.billing import ensure_admin_emails
    await ensure_admin_emails()
    from .services.stripe_service import ensure_stripe_products
    await ensure_stripe_products()
    await heartbeat_service.start()
    try:
        key = get_access_key()
        print(f"[auth] Access key: {key}")
    except Exception:
        pass
    yield
    await heartbeat_service.stop()
    await engine.dispose()
    print("[python] FastAPI shutdown")


app = FastAPI(title="A0P Python Backend", lifespan=lifespan)

_allowed_origins = []
_domains = os.environ.get("REPLIT_DOMAINS", "")
if _domains:
    _allowed_origins = [f"https://{d}" for d in _domains.split(",")]
_allowed_origins.append("http://localhost:5000")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(ReplitAuthMiddleware)

for r in ALL_ROUTERS:
    app.include_router(r)


@app.get("/api/auth/debug-headers")
async def debug_headers(request: Request):
    return dict(request.headers)


@app.get("/api/auth/user")
async def auth_user(request: Request):
    user_id = request.headers.get("x-replit-user-id", "")
    if not user_id:
        return JSONResponse(status_code=401, content={"error": "Not authenticated"})
    return {
        "id": user_id,
        "email": request.headers.get("x-replit-user-email"),
        "firstName": request.headers.get("x-replit-user-name", "Operator"),
        "lastName": None,
        "profileImageUrl": request.headers.get("x-replit-user-profile-image"),
        "createdAt": None,
        "updatedAt": None,
    }


@app.post("/api/auth/login")
async def key_login(request: Request):
    """
    Key-based login. Accepts JSON {"key": "XXXX-XXXX"}.
    Returns 200 + sets session cookie on success, 401 on failure.
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "Invalid JSON"})

    provided_key = body.get("key", "").strip()
    if not provided_key or not verify_access_key(provided_key):
        return JSONResponse(status_code=401, content={"error": "Invalid access key"})

    user_id = os.environ.get("REPLIT_USERID", "operator")
    user_name = os.environ.get("REPLIT_USER", "Operator")
    admin_email = os.environ.get("ADMIN_EMAIL", "")

    user_info = {
        "id": user_id,
        "email": admin_email or None,
        "firstName": user_name,
        "lastName": None,
        "profileImageUrl": None,
    }

    cookie_value = make_session_cookie(user_info)
    response = JSONResponse(content={"ok": True, "user": user_info})
    response.set_cookie(
        key=SESSION_COOKIE,
        value=cookie_value,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 7,
        path="/",
    )
    print(f"[auth] Session created for {user_name} ({user_id})")
    return response


@app.get("/api/login")
async def login_redirect():
    return RedirectResponse(url="/login", status_code=302)


@app.get("/api/logout")
async def logout(request: Request):
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie(key=SESSION_COOKIE, path="/")
    return response


@app.get("/api/health")
async def health():
    pcna = get_pcna()
    provider = energy_registry.get_active_provider()
    return {
        "status": "ok",
        "service": "python-backend",
        "pcna": "online",
        "instance_id": pcna.guardian.instance_id,
        "agent": compose_name(provider),
        "energy_provider": provider,
        "uptime_s": round(time.time() - pcna.created_at, 1),
        "heartbeat": heartbeat_service.status(),
    }


@app.get("/api/v1/ui/structure")
async def ui_structure():
    return {
        "tabs": collect_ui_meta(),
        "agent": compose_name(energy_registry.get_active_provider()),
        "version": "2.0.0",
    }


STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "dist", "public")
if os.path.isdir(STATIC_DIR):
    app.mount("/assets", StaticFiles(directory=os.path.join(STATIC_DIR, "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        return FileResponse(os.path.join(STATIC_DIR, "index.html"))
