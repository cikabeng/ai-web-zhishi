"""OpenAI 兼容的聊天客户端。

设计取舍：
- 只用最小公共子集（messages / temperature / max_tokens），不依赖 function calling；
- 任何失败都抛 LLMError，由教学引擎回退到模板，保证"模型挂了系统还能用"；
- 不做流式（当前回答是结构化块），避免把简单链路复杂化。
"""

from __future__ import annotations

import time
from typing import Any

import httpx

from app.core.config import Settings, get_settings
from app.llm.prompts import build_messages
from app.teaching.types import RetrievedChunk


class LLMError(RuntimeError):
    """模型不可用或返回异常，调用方应回退到模板。"""


class LLMClient:
    def __init__(self, settings: Settings | None = None, transport: httpx.BaseTransport | None = None) -> None:
        self.settings = settings or get_settings()
        self._transport = transport

    @property
    def available(self) -> bool:
        """配置齐全且没有强制演示模式时才真正调用模型。"""
        return self.settings.llm_configured and not self.settings.demo_mode

    @property
    def model_name(self) -> str:
        return self.settings.llm_model

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        url = f"{self.settings.llm_base_url.rstrip('/')}/chat/completions"
        payload: dict[str, Any] = {
            "model": self.settings.llm_model,
            "messages": messages,
            "temperature": self.settings.llm_temperature if temperature is None else temperature,
            "max_tokens": max_tokens or self.settings.llm_max_tokens,
            "stream": False,
        }
        headers = {
            "Authorization": f"Bearer {self.settings.llm_api_key}",
            "Content-Type": "application/json",
        }

        last_error: Exception | None = None
        for attempt in range(2):
            try:
                with httpx.Client(timeout=self.settings.llm_timeout, transport=self._transport) as client:
                    response = client.post(url, json=payload, headers=headers)
                    response.raise_for_status()
                    data = response.json()
                content = data["choices"][0]["message"]["content"]
                text = (content or "").strip()
                if not text:
                    raise LLMError("模型返回空内容")
                return text
            except LLMError:
                raise
            except Exception as exc:  # 网络错误、超时、4xx/5xx、结构不符
                last_error = exc
                if attempt == 0:
                    time.sleep(0.5)
                    continue
                raise LLMError(f"模型调用失败：{exc}") from exc

        raise LLMError(f"模型调用失败：{last_error}")

    def compose_hint(
        self,
        *,
        question: str,
        level: int,
        category_label: str,
        mode: str,
        chunks: list[RetrievedChunk],
        attempt: str | None = None,
    ) -> str:
        messages = build_messages(
            question=question,
            level=level,
            category_label=category_label,
            mode=mode,
            chunks=chunks,
            attempt=attempt,
        )
        return self.chat(messages, max_tokens=min(self.settings.llm_max_tokens, 700))
