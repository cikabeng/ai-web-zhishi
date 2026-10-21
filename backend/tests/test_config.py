"""配置与演示模式开关测试。

所有用例都显式 `_env_file=None`，不读本机 .env，保证换一台机器结果一致。
"""

from __future__ import annotations

from app.core.config import Settings


def test_demo_mode_defaults_to_auto() -> None:
    settings = Settings(_env_file=None, DEMO_MODE="auto")
    # 没有配 Key 时应自动进入演示模式
    assert settings.llm_configured is False
    assert settings.demo_mode is True


def test_demo_mode_auto_off_when_model_configured() -> None:
    settings = Settings(
        _env_file=None,
        DEMO_MODE="auto",
        LLM_API_KEY="sk-test",
        LLM_BASE_URL="http://localhost:1/v1",
        LLM_MODEL="demo-model",
    )
    assert settings.llm_configured is True
    assert settings.demo_mode is False


def test_demo_mode_can_be_forced_on_even_with_key() -> None:
    settings = Settings(
        _env_file=None,
        DEMO_MODE="on",
        LLM_API_KEY="sk-test",
        LLM_BASE_URL="http://localhost:1/v1",
        LLM_MODEL="demo-model",
    )
    assert settings.llm_configured is True
    # 现场 API 故障时强制演示模式，界面必须明确标注
    assert settings.demo_mode is True


def test_demo_mode_can_be_forced_off() -> None:
    settings = Settings(_env_file=None, DEMO_MODE="off")
    assert settings.demo_mode is False


def test_upload_limits_are_sane() -> None:
    settings = Settings(_env_file=None)
    assert settings.upload_max_bytes == settings.upload_max_mb * 1024 * 1024
    assert settings.ocr_max_bytes == settings.ocr_max_image_mb * 1024 * 1024
