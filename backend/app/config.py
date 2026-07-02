"""Application configuration via pydantic-settings — grouped by module.

Environment variables map with prefixes for each group:
    APP_*, DB_*, DEEPSEEK_*, KB_*, OCR_*, AGENT_*, PII_*
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


# ---------------------------------------------------------------------------
# Sub-config groups (each needs its own env_file — pydantic-settings
# does NOT inherit model_config from containing classes)
# ---------------------------------------------------------------------------

class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    env: str = Field(default="development", alias="app_env")
    secret_key: str = Field(default="change-me-in-production", alias="app_secret_key")
    host: str = Field(default="0.0.0.0", alias="app_host")
    port: int = Field(default=8000, alias="app_port")


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    url: str = Field(default="sqlite:///./expense_reimbursement.db", alias="database_url")


class DeepSeekSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    api_key: str = Field(default="", alias="deepseek_api_key")
    model: str = Field(default="deepseek-chat", alias="deepseek_model")
    base_url: str = Field(default="https://api.deepseek.com/v1", alias="deepseek_base_url")


class KBSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    chunk_size: int = Field(default=500, alias="kb_chunk_size")
    chunk_overlap: int = Field(default=50, alias="kb_chunk_overlap")
    top_k: int = Field(default=5, alias="kb_top_k")
    embedding_model: str = Field(
        default="paraphrase-multilingual-MiniLM-L12-v2",
        alias="kb_embedding_model",
    )
    chroma_path: str = Field(default="./data/chroma", alias="kb_chroma_path")


class OCRSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    engine: str = Field(default="easyocr", alias="ocr_engine")


class AgentSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    max_retries: int = Field(default=2, alias="agent_max_retries")
    cloud_timeout_seconds: int = Field(default=30, alias="agent_cloud_timeout_seconds")


class PIISettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    mapping_retention_days: int = Field(default=7, alias="pii_mapping_retention_days")


class FileStorageSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    invoice_storage_path: str = Field(default="./data/invoices", alias="invoice_storage_path")


class PolicySettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    policies_dir: str = Field(default="./policies", alias="policy_policies_dir")
    policy_storage_backend: str = Field(default="json", alias="policy_storage_backend")


# ---------------------------------------------------------------------------
# Root settings — combines all groups
# ---------------------------------------------------------------------------

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app: AppSettings = AppSettings()
    db: DatabaseSettings = DatabaseSettings()
    deepseek: DeepSeekSettings = DeepSeekSettings()
    kb: KBSettings = KBSettings()
    ocr: OCRSettings = OCRSettings()
    agent: AgentSettings = AgentSettings()
    pii: PIISettings = PIISettings()
    storage: FileStorageSettings = FileStorageSettings()
    policy: PolicySettings = PolicySettings()


settings = Settings()
