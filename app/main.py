from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.routes import consent, accounts, score, health, self_reported, users, auth, passport, whatsapp

# Fails fast at boot if production config is unsafe (placeholder secrets,
# identical signing keys, wide-open CORS, DEBUG leaking OTPs) — better to
# refuse to start than to silently run insecurely.
settings.validate_production_safety()

app = FastAPI(
    title=settings.APP_NAME,
    description="Worker-owned financial passport & explainable credit score for gig workers.",
    version=settings.MODEL_VERSION,
)

# CORS: explicit allow-list takes priority whenever it's set (works in any
# environment). With no allow-list configured, DEBUG mode falls back to
# wide-open for local dev convenience; anything else defaults to blocking
# all cross-origin requests rather than silently allowing them.
if settings.CORS_ALLOWED_ORIGINS:
    _allowed_origins = [o.strip() for o in settings.CORS_ALLOWED_ORIGINS.split(",") if o.strip()]
elif settings.DEBUG:
    _allowed_origins = ["*"]
else:
    _allowed_origins = []

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, tags=["health"])
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(users.router, prefix="/api/v1/users", tags=["users"])
app.include_router(consent.router, prefix="/api/v1/consent", tags=["consent"])
app.include_router(accounts.router, prefix="/api/v1/accounts", tags=["accounts"])
app.include_router(score.router, prefix="/api/v1/score", tags=["score"])
app.include_router(self_reported.router, prefix="/api/v1/self-reported", tags=["self-reported"])
app.include_router(passport.router, prefix="/api/v1/passport", tags=["passport"])
app.include_router(whatsapp.router, prefix="/api/v1/whatsapp", tags=["whatsapp"])
