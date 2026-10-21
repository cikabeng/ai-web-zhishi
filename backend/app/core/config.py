"""全局配置。

所有环境变量集中在这里声明，其他模块只通过 `get_settings()` 读取，
避免散落各处的 os.getenv。
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# 本文件位于 backend/app/core/config.py，向上四级即项目根目录
PROJECT_ROOT = Path(__file__).resolve().parents[3]
BACKEND_DIR = PROJECT_ROOT / "backend"


class Settings(BaseSettings):
    """运行时配置，字段名与环境变量名一一对应（大小写不敏感）。"""

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---------- 应用 ----------
    app_name: str = "知实 AI"
    app_version: str = "0.1.0"
    app_env: str = "dev"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # ---------- 存储 ----------
    storage_dir: Path = Path("./storage")
    sqlite_url: str = "sqlite:///./storage/app.db"
    chroma_dir: Path = Path("./storage/chroma")

    # ---------- 上传限制 ----------
    upload_max_mb: int = 20
    upload_max_pages: int = 300
    upload_allowed_ext: str = "pdf,docx,txt,md"

    # ---------- 大模型 ----------
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    llm_temperature: float = 0.3
    llm_max_tokens: int = 1200
    llm_timeout: int = 60

    # ---------- Embedding ----------
    embed_provider: str = ""
    embed_base_url: str = ""
    embed_api_key: str = ""
    embed_model: str = "bge-m3"
    embed_dim: int = 1024
    embed_batch: int = 16

    # ---------- OCR / 图像 ----------
    ocr_provider: str = "auto"  # auto | rapidocr | vision | none
    ocr_max_image_mb: int = 8
    ocr_max_side: int = 1600
    ocr_timeout: int = 60

    # ---------- 视觉模型（可选，支持图像输入时才生效）----------
    vlm_base_url: str = ""
    vlm_api_key: str = ""
    vlm_model: str = ""

    # ---------- 检索 ----------
    retrieval_top_k: int = 6
    retrieval_min_score: float = 0.30
    max_context_chars: int = 6000

    # ---------- 教学策略 ----------
    guided_require_attempt: bool = True
    max_hint_level: int = 4
    leak_guard_enabled: bool = True

    # ---------- 派生属性 ----------

    @field_validator("storage_dir", "chroma_dir", mode="after")
    @classmethod
    def _resolve_relative_path(cls, value: Path) -> Path:
        """把相对路径统一解析到项目根目录下，避免受启动目录影响。"""
        path = Path(value)
        return path if path.is_absolute() else (PROJECT_ROOT / path).resolve()

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def allowed_ext_list(self) -> list[str]:
        return [item.strip().lower().lstrip(".") for item in self.upload_allowed_ext.split(",") if item.strip()]

    @property
    def llm_configured(self) -> bool:
        """三项齐全才认为大模型可用。"""
        return bool(self.llm_api_key.strip() and self.llm_base_url.strip() and self.llm_model.strip())

    @property
    def resolved_embed_provider(self) -> str:
        """显式配置优先；未配置时按是否有 API Key 自动选择。"""
        provider = self.embed_provider.strip().lower()
        if provider in {"api", "hash"}:
            return provider
        return "api" if self.embed_api_key.strip() else "hash"

    @property
    def demo_mode(self) -> bool:
        """未配置大模型即演示模式：检索真实执行，回答由模板生成。"""
        return not self.llm_configured

    @property
    def vlm_configured(self) -> bool:
        """三项齐全才认为视觉模型可用。"""
        return bool(self.vlm_api_key.strip() and self.vlm_base_url.strip() and self.vlm_model.strip())

    @property
    def ocr_max_bytes(self) -> int:
        return self.ocr_max_image_mb * 1024 * 1024

    @property
    def upload_max_bytes(self) -> int:
        return self.upload_max_mb * 1024 * 1024


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
