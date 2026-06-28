from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "HealthAI Coaching API"
    api_prefix: str = "/api"
    environment: str = "development"
    database_url: str | None = None
    db_host: str = "127.0.0.1"
    db_port: int = 3306
    db_user: str = "root"
    db_password: str = ""
    db_name: str = "healthai_coaching"
    jwt_secret_key: str = Field(default="change-me-in-production")
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 30
    refresh_token_days: int = 7
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    log_level: str = "INFO"
    log_json: bool = False
    password_reset_token_minutes: int = 30
    media_root: str = "data"
    media_base_url: str = "http://localhost:8000"
    ai_enable_external_calls: bool = False
    hf_token: str | None = None
    huggingface_api_token: str | None = None
    huggingface_vision_model: str = "nateraw/food"
    huggingface_vision_model_fallbacks: str | None = None
    meal_hf_base_url: str = "https://router.huggingface.co/v1"
    meal_hf_vision_model: str | None = None
    meal_hf_vision_model_fallbacks: str | None = None
    meal_hf_serverless_url: str = "https://api-inference.huggingface.co/models"
    meal_hf_caption_model: str = "Salesforce/blip-image-captioning-base"
    deepseek_api_key: str | None = None
    deepseek_base_url: str | None = None
    deepseek_model: str | None = None
    meal_llm_base_url: str | None = None
    meal_llm_model: str | None = None
    meal_ai_timeout_seconds: float = 30.0
    meal_ai_max_image_bytes: int = 6_000_000
    meal_ai_force_mock: bool = False
    gemini_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:1b"
    mongo_url: str = "mongodb://localhost:27017"
    mongo_db_name: str = "healthai_nosql"
    mongo_enabled: bool = True
    mongo_timeout_ms: int = 800

    model_config = SettingsConfigDict(
        env_file=("healthai_etl/.env", "backend/.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def sqlalchemy_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return (
            f"mysql+pymysql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}?charset=utf8mb4"
        )

    @property
    def effective_huggingface_token(self) -> str | None:
        return self.hf_token or self.huggingface_api_token

    @property
    def effective_vision_model(self) -> str:
        return self.huggingface_vision_model or self.meal_hf_vision_model or "nateraw/food"

    @property
    def effective_vision_fallback_models(self) -> list[str]:
        configured = self.huggingface_vision_model_fallbacks or self.meal_hf_vision_model_fallbacks
        default = "prithivMLmods/Food-101-93M,nateraw/vit-base-food101"
        return [
            model.strip()
            for model in (configured or default).split(",")
            if model.strip()
        ]

    @property
    def effective_vision_models(self) -> list[str]:
        models: list[str] = []
        for model in [self.effective_vision_model, *self.effective_vision_fallback_models]:
            if model and model not in models:
                models.append(model)
        return models

    @property
    def effective_deepseek_base_url(self) -> str:
        return self.deepseek_base_url or self.meal_llm_base_url or "https://api.deepseek.com"

    @property
    def effective_deepseek_model(self) -> str:
        return self.deepseek_model or self.meal_llm_model or "deepseek-chat"


@lru_cache
def get_settings() -> Settings:
    return Settings()
