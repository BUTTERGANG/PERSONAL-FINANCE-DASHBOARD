from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Plaid
    plaid_client_id: str = ""
    plaid_secret: str = ""
    plaid_env: str = "sandbox"

    # Fidelity OFX direct connect
    fidelity_user: str = ""
    fidelity_pin: str = ""
    fidelity_account_id: str = ""

    # Encryption — generate with: python scripts/generate_key.py
    encryption_key: str = ""

    # App
    database_url: str = "sqlite:///./finance.db"
    sync_interval_hours: int = 4
    backend_url: str = "http://localhost:8000"
    app_base_url: str = "http://localhost:8501"

    # Dashboard PIN gate (frontend). Empty = no gate (dashboard is open).
    dashboard_pin: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
