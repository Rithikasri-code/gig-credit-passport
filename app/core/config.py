"""
Central configuration for the app.
All environment-specific values are loaded from .env — nothing sensitive
is hardcoded, so this file is safe to commit.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    APP_NAME: str = "Gig Credit Passport"
    ENV: str = "development"  # development | staging | production
    DEBUG: bool = True

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/gigpassport"

    # Auth
    SECRET_KEY: str = "CHANGE_ME_IN_ENV"  # noqa: S105 — placeholder, overridden by .env
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24h

    # Passport signing — deliberately SEPARATE from SECRET_KEY. Reusing one
    # secret for both JWT auth and passport HMAC signing means a leak of
    # either purpose compromises the other; keeping them independent means
    # rotating one (e.g. after a suspected leak) doesn't force rotating
    # the other, and a bug in one signing path can't forge tokens for the
    # other purpose.
    PASSPORT_SIGNING_KEY: str = "CHANGE_ME_PASSPORT_KEY_IN_ENV"  # noqa: S105

    # CORS — comma-separated list of allowed origins in production.
    # Empty/unset means "no explicit allow-list", which main.py treats as
    # DEBUG-only wide-open; production deployments MUST set this.
    CORS_ALLOWED_ORIGINS: str = ""

    # Account Aggregator (Setu sandbox by default)
    AA_PROVIDER: str = "setu"  # setu | finvu | onemoney
    AA_BASE_URL: str = "https://fiu-sandbox.setu.co"
    AA_CLIENT_ID: str = ""
    AA_CLIENT_SECRET: str = ""
    AA_PRODUCT_INSTANCE_ID: str = ""

    # Scoring
    MODEL_PATH: str = "app/scoring/artifacts/model.pkl"
    MODEL_VERSION: str = "v0.2.0"

    def validate_production_safety(self) -> None:
        """
        Called at app startup. Refuses to boot in production with any of
        the placeholder secrets still in place, or with the two signing
        keys accidentally identical — cheap insurance against the most
        common "forgot to configure this" deployment mistake.
        """
        if self.ENV != "production":
            return

        problems = []
        if self.SECRET_KEY == "CHANGE_ME_IN_ENV":
            problems.append("SECRET_KEY is still the placeholder value")
        if self.PASSPORT_SIGNING_KEY == "CHANGE_ME_PASSPORT_KEY_IN_ENV":
            problems.append("PASSPORT_SIGNING_KEY is still the placeholder value")
        if self.SECRET_KEY == self.PASSPORT_SIGNING_KEY:
            problems.append("SECRET_KEY and PASSPORT_SIGNING_KEY must be different values")
        if not self.CORS_ALLOWED_ORIGINS:
            problems.append("CORS_ALLOWED_ORIGINS must be set explicitly in production")
        if self.DEBUG:
            problems.append("DEBUG must be false in production (it currently leaks OTPs in API responses)")

        if problems:
            raise RuntimeError(
                "Refusing to start in production with unsafe configuration:\n"
                + "\n".join(f"  - {p}" for p in problems)
            )


settings = Settings()
