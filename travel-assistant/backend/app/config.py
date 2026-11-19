from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = "智能旅行助手"
    env: str = "development"
    data_dir: Path = ROOT / "backend" / "data"
    database_url: str = ""

    amap_key: str = ""
    amap_web_key: str = ""

    llm_api_key: str = ""
    llm_base_url: str = "https://api.deepseek.com/v1"
    llm_model: str = "deepseek-chat"

    chrome_bin: str = ""
    demo_city: str = "成都"
    session_cookie: str = "ta_sid"
    session_days: int = 30
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    model_config = SettingsConfigDict(
        env_file=ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def database(self) -> str:
        if self.database_url:
            return self.database_url
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return f"sqlite+aiosqlite:///{self.data_dir / 'app.db'}"

    @property
    def amap_web_key_effective(self) -> str:
        return self.amap_web_key or self.amap_key

    @property
    def amap_configured(self) -> bool:
        return bool(self.amap_web_key_effective)

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_api_key)

    @property
    def origins(self) -> list[str]:
        return [x.strip() for x in self.cors_origins.split(",") if x.strip()]


settings = Settings()
settings.data_dir.mkdir(parents=True, exist_ok=True)
(settings.data_dir / "exports").mkdir(parents=True, exist_ok=True)
