from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
_REPO_POLICY_DIR = PROJECT_ROOT / "data" / "policies"
_PACKAGED_POLICY_DIR = Path(__file__).resolve().parent / "policies"
_DEFAULT_POLICY_DIR = _REPO_POLICY_DIR if _REPO_POLICY_DIR.is_dir() else _PACKAGED_POLICY_DIR


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "banking-agent-observability"
    environment: str = "development"
    host: str = "0.0.0.0"
    port: int = 8000
    database_path: Path = PROJECT_ROOT / "data" / "banking_agent.sqlite3"
    adk_sessions_db_path: Path = PROJECT_ROOT / "data" / "adk_sessions.sqlite3"
    policy_data_dir: Path = Field(default=_DEFAULT_POLICY_DIR, alias="POLICY_DATA_DIR")
    google_api_key: str | None = Field(default=None, alias="GOOGLE_API_KEY")
    model_name: str = "gemini-2.5-flash"
    arize_space_id: str | None = Field(default=None, alias="ARIZE_SPACE_ID")
    arize_api_key: str | None = Field(default=None, alias="ARIZE_API_KEY")
    arize_project_name: str = "banking-agent-observability"
    arize_endpoint: str | None = Field(default=None, alias="ARIZE_COLLECTOR_ENDPOINT")
    trace_console: bool = True
    capture_trace_content: bool = False
    allowed_demo_customers: str = "cust_1001,cust_1002"
    max_request_chars: int = 5000

    @property
    def demo_customer_ids(self) -> set[str]:
        return {item.strip() for item in self.allowed_demo_customers.split(",") if item.strip()}

    @property
    def arize_configured(self) -> bool:
        return bool(self.arize_space_id and self.arize_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
